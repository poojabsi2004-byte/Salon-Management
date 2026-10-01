# -*- coding: utf-8 -*-
"""Serve the Enrich Beauty design, backed by live salon data.

The whole site is one self-contained HTML asset (markup, styles, scripts and
images are all inlined). It is still served verbatim in every visual respect --
nothing is re-implemented in QWeb, so nothing can drift from the approved design.

PHASE 1 BRIDGE adds a data layer on top of that. Before the file goes out, the
JavaScript literals the design was built against (CITIES, SERVICES_DATA,
STYLISTS, TIERS_DATA, TIME_SLOTS) are swapped for the equivalent records from
bsi_salon_backend, and the three dead controls are given real backend calls. The
markup, styles and every pixel of layout are untouched -- only the values behind
them change.

The substitution happens on the served bytes, never on the file: static/src/
enrich_site.html is compiled output and stays exactly as exported.

The five endpoints below replace the ones removed from bsi_salon_backend when its
website layer was stripped. The booking rules they depend on still live on
bsi.salon.booking.mixin, so these are thin wrappers over that logic rather than
reimplementations of it.
"""

import json
import math
import logging
import re

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import file_open
from odoo.tools.sql import escape_psql

from . import enrich_patches
from . import enrich_redesign
from . import enrich_hero
from . import enrich_loyalty
from . import enrich_confirm
from . import enrich_extensions

_logger = logging.getLogger(__name__)

SITE_ASSET = 'bsi_salon_web/static/src/enrich_site.html'

# The design's data lives inside a JSON-encoded <script type="__bundler/template">
# block, so the page source has to be decoded before it can be edited and
# re-encoded afterwards.
_TEMPLATE_RE = re.compile(
    r'(<script[^>]*type="__bundler/template"[^>]*>)(.*?)(</script>)',
    re.DOTALL,
)

# PHASE 1 BRIDGE -- the assembled page is ~19 MB and rebuilding it means decoding
# and re-encoding the template on every hit, so it is cached.
#
# The cache is shared by every visitor, so nothing visitor-specific may ever be
# baked in here. Loyalty balances in particular stay as the design's sample
# figure: injecting a signed-in customer's real points would serve them to
# everyone. Anything per-user has to be fetched at runtime instead.
_PAGE_CACHE = {'key': None, 'html': None}


def _js_safe(dumped):
    """Escape a closing script tag inside generated JavaScript.

    A record whose text contains "</script>" would otherwise close the block the
    moment the browser parsed it, truncating the page. "\\/" is an identity
    escape in both JSON and JavaScript, so the value itself is unchanged.
    """
    return dumped.replace('</', r'<\/')


def _replace_value_at(source, anchor, value, raw=False):
    """Swap the bracketed literal that starts right after `anchor`.

    Scans balanced brackets rather than pattern-matching the body, because these
    literals contain nested arrays, objects and apostrophes in the copy. With
    raw=True, `value` is spliced in verbatim as JavaScript source (e.g. a bare
    identifier) instead of being JSON-encoded.
    """
    start = source.find(anchor)
    if start == -1:
        _logger.warning('Enrich site: anchor %r not found, leaving design default', anchor)
        return source

    open_at = start + len(anchor)
    if open_at >= len(source) or source[open_at] not in '[{':
        _logger.warning('Enrich site: anchor %r has an unexpected shape', anchor)
        return source

    opening = source[open_at]
    closing = {'[': ']', '{': '}'}[opening]
    depth, index, quote = 0, open_at, None
    while index < len(source):
        char = source[index]
        if quote:
            if char == '\\':
                index += 2
                continue
            if char == quote:
                quote = None
        elif char in '"\'`':
            quote = char
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                break
        index += 1

    if depth != 0:
        _logger.warning('Enrich site: could not delimit value after %r', anchor)
        return source

    literal = value if raw else _js_safe(json.dumps(value, ensure_ascii=False))
    return source[:open_at] + literal + source[index + 1:]


def _replace_literal(source, name, value):
    """PHASE 1 BRIDGE -- swap `const NAME = <literal>;` for live data."""
    return _replace_value_at(source, 'const %s = ' % name, value)


def _replace_property(source, key, value):
    """PHASE 2 DEV -- swap a `key: <literal>` object property for live data.

    Same idea as _replace_literal, but for values the design carries as a
    property inside a bigger render-time object rather than a top-level const.
    """
    return _replace_value_at(source, '%s: ' % key, value)


def _replace_property_ref(source, key, const_name):
    """PHASE 2 DEV -- point a `key: [...]` property at an injected top-level const.

    Used where the array literal is immediately chained with `.map(...)` that
    must survive the swap -- the finish/length pickers build their button
    styling that way, so only the catalogue itself is replaced.
    """
    return _replace_value_at(source, '%s: ' % key, const_name, raw=True)


_DEFAULT_LOOK_FINISHES = [
    {'id': 'gloss', 'label': 'High Gloss', 'surcharge': 400},
    {'id': 'matte', 'label': 'Soft Matte', 'surcharge': 0},
    {'id': 'wave', 'label': 'Beach Wave', 'surcharge': 900},
]
_DEFAULT_LOOK_LENGTHS = [
    {'id': 'long', 'label': 'Long', 'sub': 'Past the shoulder', 'surcharge': 600},
    {'id': 'mid', 'label': 'Shoulder', 'sub': 'The classic', 'surcharge': 300},
    {'id': 'short', 'label': 'Short', 'sub': 'Sharp and light', 'surcharge': 0},
]
_DEFAULT_LOOK_BASE_PRICE = 2999


def _inject_look_consts(page, data):
    """PHASE 2 DEV -- new top-level consts for the finish/length pickers.

    Unlike the substitutions above, these have no design-authored fallback
    left in the page once the picker literals are pointed at them, so they are
    always injected -- defaulting to the design's own three-of-each so a fresh
    database with no records yet still renders exactly as before.

    Spliced into the actual `<script type="text/x-dc">` component logic, not
    prepended to the page -- the served document is markup first and that
    script block second (see BsiSalonWeb._render_site), so text prepended to
    `page` itself lands before <!DOCTYPE html>, never executes, and every
    reference to these consts fails at runtime with a ReferenceError.
    """
    finishes = data.get('look_finishes') or _DEFAULT_LOOK_FINISHES
    lengths = data.get('look_lengths') or _DEFAULT_LOOK_LENGTHS
    base_price = data.get('look_base_price') or _DEFAULT_LOOK_BASE_PRICE
    rules = data.get('consult_rules') or []
    # The ritual builder's own ADDONS const (see enrich_patches's chair-side ritual
    # builder patches) is declared inside a render-time closure, out of reach of the
    # booking wizard's Confirm-screen total a few closures over -- this top-level copy
    # is what that total reads add-on prices from instead (see BASEPRICE_DST).
    addons = data.get('addons') or []
    # PHASE 5 DEV -- packages have no design-authored literal to swap at all (the
    # design predates the feature), so they're injected the same way as the
    # consult rules/add-ons above rather than going through _replace_literal.
    packages = data.get('packages') or []
    # About page and customer-care details (see bsi.enrich.data._bsi_about_page /
    # _bsi_contact); both carry their own design fallbacks.
    about = data.get('about_page') or {}
    contact = data.get('contact') or {}
    consts = (
        ('BSI_LOOK_FINISHES', finishes),
        ('BSI_LOOK_LENGTHS', lengths),
        ('BSI_LOOK_BASE_PRICE', base_price),
        ('BSI_CONSULT_RULES', rules),
        ('BSI_ADDONS', addons),
        ('BSI_PACKAGES', packages),
        ('BSI_ABOUT', about),
        ('BSI_CONTACT', contact),
        # The Colour Lab's price/time table (bsi.salon.colour.lab.config): labPlan()
        # prices the estimate from it and _bsi_resolve_colour_lab re-prices a "Book a
        # colour consultation" booking from the very same figures (see
        # enrich_redesign.COLOUR_LAB_PATCHES).
        ('BSI_LAB_PRICING', data.get('lab_pricing') or {}),
    )
    injected = ''.join(
        'const %s = %s;\n' % (name, _js_safe(json.dumps(value, ensure_ascii=False)))
        for name, value in consts
    )

    anchor = '<script type="text/x-dc"'
    tag_start = page.find(anchor)
    if tag_start == -1:
        _logger.warning('Enrich site: %s not found, look/consult catalogue not injected', anchor)
        return page
    tag_close = page.find('>', tag_start)
    if tag_close == -1:
        _logger.warning('Enrich site: %s has no closing >, look/consult catalogue not injected', anchor)
        return page
    insert_at = tag_close + 1
    return page[:insert_at] + injected + page[insert_at:]


class BsiSalonWeb(http.Controller):

    # ------------------------------------------------------------------
    # PHASE 1 BRIDGE -- page assembly
    # ------------------------------------------------------------------

    def _build_site(self):
        """Read the exported design and substitute live values into it."""
        with file_open(SITE_ASSET, 'r') as handle:
            raw = handle.read()

        match = _TEMPLATE_RE.search(raw)
        if not match:
            _logger.warning('Enrich site: template block not found, serving design as exported')
            return raw

        try:
            page = json.loads(match.group(2))
        except ValueError:
            _logger.warning('Enrich site: template block is not valid JSON, serving as exported')
            return raw

        data = request.env['bsi.enrich.data'].sudo()._bsi_payload()

        # Only substitute what actually came back. An empty dataset means the
        # salon backend holds no records of that kind yet, and the design's own
        # sample data makes a better page than an empty one.
        for literal, key in (
            # PHASE 1 BRIDGE
            ('CITIES', 'cities'), ('SERVICES_DATA', 'services'),
            ('STYLISTS', 'stylists'), ('TIERS_DATA', 'tiers'),
            ('TIME_SLOTS', 'slot_labels'),
            # PHASE 2 DEV -- content the design used to carry itself
            ('CITY_IDENTITY', 'city_identity'), ('CHAIR_STYLES', 'chair_styles'),
            ('REVIEWS', 'reviews'), ('ADDONS', 'addons'),
            ('LEVELS', 'colour_levels'), ('TONES', 'colour_tones'),
            ('CONDITIONS', 'hair_conditions'), ('LOOK_SHADES', 'look_shades'),
            ('GIFT_MESSAGES', 'gift_messages'), ('WALLET_REWARDS', 'loyalty_rewards'),
            ('Q', 'consult_questions'), ('giftAmounts', 'gift_amounts'),
        ):
            if data.get(key):
                page = _replace_literal(page, literal, data[key])

        # PHASE 2 DEV -- values the design carries as an inline object property
        # rather than a top-level const (see _replace_property).
        for prop, key in (
            ('galleryItems', 'transformations'),
        ):
            if data.get(key):
                page = _replace_property(page, prop, data[key])

        # About page lists: the design's literals stay as the fallback for any list
        # the backend has no records for yet.
        about = data.get('about_page') or {}
        for prop, key in (
            ('aboutStats', 'stats'), ('aboutTimeline', 'timeline'), ('aboutAwards', 'awards'),
            # The home banner's four numbers come from the same Headline Numbers.
            ('heroStats', 'heroStats'),
        ):
            if about.get(key):
                page = _replace_property(page, prop, about[key])

        # PHASE 2 DEV -- the look configurator's finish/length pickers and the
        # pricing maths that used to hardcode the same three-of-each now both
        # read one injected catalogue.
        page = _inject_look_consts(page, data)
        page = _replace_property_ref(page, 'lookFinishes', 'BSI_LOOK_FINISHES')
        page = _replace_property_ref(page, 'lookLengths', 'BSI_LOOK_LENGTHS')

        # Each patch applies only if its exact anchor is still present, so a
        # re-exported design degrades to its original behaviour instead of
        # failing to load.
        for label, source, target in enrich_patches.PATCHES:
            if source in page:
                page = page.replace(source, target, 1)
            else:
                _logger.warning('Enrich site: %s not found, left as designed', label)

        for label, source, target in enrich_redesign.PATCHES:
            if source in page:
                page = page.replace(source, target, 1)
            else:
                _logger.warning('Enrich site: %s not found, left as designed', label)

        for label, anchor, open_tag, close_tag, target in enrich_redesign.BLOCK_PATCHES:
            patched = enrich_redesign.apply_block_patch(page, anchor, open_tag, close_tag, target)
            if patched is None:
                _logger.warning('Enrich site: %s not found, left as designed', label)
            else:
                page = patched

        # Home banner, live strip and services marquee (see enrich_hero) -- last, so
        # its anchors match the fully patched template.
        page = enrich_hero.apply(page, data)

        # Loyalty on the website: per-service points opt-in, multi-service rewards and
        # the live points balance (see enrich_loyalty) -- after the hero, before the
        # Confirm-step redesign, so its anchors match the patched loyalty markup.
        page = enrich_loyalty.apply(page, data)

        # Confirm step v2 (signed-in details, required-data checklist), site-wide
        # bsiToast() and the backend-toggle clean-up (see enrich_confirm) -- after
        # every design/loyalty patch above, since its anchors match their output.
        page = enrich_confirm.apply(page, data)

        # Sign-in gate (see enrich_auth): guests browse freely but must sign in to
        # book, buy a membership / gift card or use points. Runs after
        # enrich_confirm -- it guards the final Confirm handler and extends that
        # step's .bsi-cf-signin card. Imported here, not at the top: enrich_auth
        # subclasses this controller (it is loaded from controllers/__init__.py).
        from . import enrich_auth
        page = enrich_auth.apply(page, data)

        # Per-feature patch modules (stylists, portfolio booking, recommended,
        # featured services, offers -- see enrich_extensions), last of all.
        page = enrich_extensions.apply(page, data)

        # The block holds a complete JSON string literal, quotes included, so the
        # replacement keeps the quotes json.dumps puts back.
        html = raw[:match.start(2)] + _js_safe(json.dumps(page)) + raw[match.end(2):]

        # Patches on the outer bundler shell (first-paint HTML, outside the
        # template), e.g. its loading splash.
        for label, source, target in enrich_redesign.OUTER_PATCHES:
            if source in html:
                html = html.replace(source, target, 1)
            else:
                _logger.warning('Enrich site: %s not found, left as designed', label)

        # Section-visibility CSS injection — hide website sections when their
        # config toggle is off (see res_config_settings.py BSI_SHOW_PARAM_KEYS).
        ICP = request.env['ir.config_parameter'].sudo()
        hide_selectors = []
        if ICP.get_param('bsi_salon_backend.show_design_your_look', 'True') != 'True':
            hide_selectors.append('[data-screen-label="Design your look"]')
        if ICP.get_param('bsi_salon_backend.show_colour_lab', 'True') != 'True':
            hide_selectors.append('[data-screen-label="Colour Lab"]')
        if ICP.get_param('bsi_salon_backend.show_transformation', 'True') != 'True':
            hide_selectors.append('.bsi-tf')
        if hide_selectors:
            hide_css = '<style>%s{display:none!important}</style>' % ','.join(hide_selectors)
            html = html.replace('</helmet>', hide_css + '</helmet>', 1)

        return html

    def _render_site(self):
        key = request.env['bsi.enrich.data'].sudo()._bsi_cache_key()
        if _PAGE_CACHE['key'] != key or not _PAGE_CACHE['html']:
            _PAGE_CACHE['html'] = self._build_site()
            _PAGE_CACHE['key'] = key
        return request.make_response(_PAGE_CACHE['html'].encode('utf-8'), headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'public, max-age=300'),
        ])

    @http.route('/salon', type='http', auth='public', website=True, sitemap=True, csrf=False)
    def bsi_salon_site(self, **kwargs):
        return self._render_site()

    # Deep links used by the design's own navigation all resolve to the same
    # single-page app, so a refresh or a shared URL never 404s.
    @http.route([
        '/salon/home',
        '/salon/stores',
        '/salon/booking',
        '/salon/membership',
        '/salon/services',
        '/salon/stylists',
        '/salon/about',
        '/salon/contact',
    ], type='http', auth='public', website=True, sitemap=False, csrf=False)
    def bsi_salon_pages(self, **kwargs):
        return self._render_site()

    # ------------------------------------------------------------------
    # PHASE 1 BRIDGE -- availability
    # ------------------------------------------------------------------

    def _bsi_conflict_probe(self, location, date_str, slot):
        """Build an unsaved lead used to ask the mixin about conflicts.

        The conflict helpers are record methods on bsi.salon.booking.mixin, so a
        NewId record is the supported way to ask "would this combination clash"
        without writing anything.
        """
        return request.env['crm.lead'].sudo().new({
            'bsi_location_id': location.id,
            'bsi_preferred_date': date_str,
            'bsi_use_slot': True,
            'bsi_slot_id': slot.id,
        })

    @http.route('/salon/api/slot_availability', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_slot_availability(self, location_id=None, preferred_date=None,
                                        chair_ids=None, artist_id=None, by_label=False, **kwargs):
        """Which fixed slots are still open at a branch on a date.

        Returns {slot_id: True/False}, or {slot label: True/False} with by_label
        (the booking wizard only knows slots by their label). A pending CRM lead
        holds a slot exactly as a confirmed appointment does -- that rule lives in
        the mixin's conflict domains and is not re-stated here.
        """
        location = request.env['bsi.salon.location'].sudo().browse(
            int(location_id) if str(location_id or '').isdigit() else 0).exists()
        booking_date, _error = self._bsi_parse_booking_date(preferred_date)
        if not location or not booking_date:
            return {}
        preferred_date = fields.Date.to_string(booking_date)

        wanted_chairs = [int(c) for c in (chair_ids or []) if str(c).isdigit()]
        artist = int(artist_id) if str(artist_id or '').isdigit() else False

        result = {}
        for slot in request.env['bsi.salon.time.slot'].sudo().search([]):
            probe = self._bsi_conflict_probe(location, preferred_date, slot)
            if wanted_chairs:
                probe.bsi_chair_ids = [(6, 0, wanted_chairs)]
            if artist:
                probe.bsi_artist_id = artist
            reason = probe._bsi_get_chair_conflict_reason() if wanted_chairs else False
            if not reason and artist:
                reason = probe._bsi_get_artist_capacity_conflict_reason()
            result[slot.id] = not reason
        if by_label:
            _labels, lookup = request.env['bsi.enrich.data'].sudo()._bsi_time_slots()
            return {label: result.get(slot_id, True) for label, slot_id in lookup.items()}
        return result

    _BSI_BOOKING_HORIZON_DAYS = 90

    def _bsi_parse_booking_date(self, value):
        """(date, error): the requested booking day, or why it can't be booked."""
        if not value:
            return None, 'Please choose a date for your appointment.'
        try:
            booking_date = fields.Date.to_date(str(value).strip()[:10])
        except (TypeError, ValueError):
            booking_date = None
        if not booking_date:
            return None, 'Please choose a valid date for your appointment.'
        today = fields.Date.context_today(request.env.user)
        if booking_date < today:
            return None, 'That date has already passed. Please choose another date.'
        if (booking_date - today).days > self._BSI_BOOKING_HORIZON_DAYS:
            return None, 'Bookings open up to %d days ahead. Please choose an earlier date.' \
                % self._BSI_BOOKING_HORIZON_DAYS
        return booking_date, None

    @http.route('/salon/api/resource_availability', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_resource_availability(self, location_id=None, preferred_date=None,
                                            slot_id=None, **kwargs):
        """Which chairs and artists are free in one slot at one branch.

        Returns {'chairs': {id: bool}, 'artists': {id: bool}}.
        """
        location = request.env['bsi.salon.location'].sudo().browse(
            int(location_id) if str(location_id or '').isdigit() else 0).exists()
        slot = request.env['bsi.salon.time.slot'].sudo().browse(
            int(slot_id) if str(slot_id or '').isdigit() else 0).exists()
        if not location or not slot or not preferred_date:
            return {'chairs': {}, 'artists': {}}

        chairs, artists = {}, {}
        for chair in request.env['bsi.salon.chair'].sudo().search(
                [('bsi_location_id', '=', location.id)]):
            probe = self._bsi_conflict_probe(location, preferred_date, slot)
            probe.bsi_chair_ids = [(6, 0, [chair.id])]
            chairs[chair.id] = not probe._bsi_get_chair_conflict_reason()

        for artist in request.env['bsi.salon.team.member'].sudo().search(
                ['|', ('bsi_location_id', '=', location.id), ('bsi_location_id', '=', False)]):
            probe = self._bsi_conflict_probe(location, preferred_date, slot)
            probe.bsi_artist_id = artist.id
            artists[artist.id] = not probe._bsi_get_artist_capacity_conflict_reason()

        return {'chairs': chairs, 'artists': artists}

    # ------------------------------------------------------------------
    # PHASE 1 BRIDGE -- submissions
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # PHASE 6 DEV -- one resolver, one server-side quote
    # ------------------------------------------------------------------
    #
    # The Confirm screen now shows loyalty-point and gift-card redemption, and
    # the site is not allowed to work out what either is worth: every figure it
    # displays comes back from /salon/api/booking_quote below, which prices the
    # selection through bsi.salon.booking.mixin itself (on an unsaved lead, the
    # same NewId probe pattern _bsi_conflict_probe already uses for availability)
    # and validates the redemption through
    # bsi.salon.loyalty.point._bsi_quote_points_redemption. /salon/api/booking
    # then resolves and validates the very same way before anything is written,
    # so a crafted request cannot redeem more than the quote offered -- the quote
    # is a preview of the server's own answer, never an input to it.

    def _bsi_resolve_look(self, look_length, look_shade_index, look_finish):
        """The Design-Your-Look picks, resolved to the one service that prices them.

        Returns None when nothing recognisable was picked. `vals` is the same
        bsi.salon.service payload a real booking creates (see
        bsi_salon_api_booking) -- the quote instantiates it unsaved instead, so
        browsing the Confirm screen never leaves stray look services behind.
        """
        Length = request.env['bsi.salon.look.length'].sudo()
        Finish = request.env['bsi.salon.look.finish'].sudo()
        lengths = Length.search([], order='sequence, id')
        shades = request.env['bsi.salon.look.shade'].sudo().search([], order='sequence, id')
        length_rec = lengths.filtered(lambda l: l.bsi_key == look_length)[:1]
        finish_rec = Finish.search([('bsi_key', '=', look_finish)], limit=1) if look_finish else Finish
        shade_rec = request.env['bsi.salon.look.shade']
        if look_shade_index is not None and str(look_shade_index).isdigit():
            index = int(look_shade_index)
            if 0 <= index < len(shades):
                shade_rec = shades[index]

        parts = [rec.name for rec in (length_rec, shade_rec, finish_rec) if rec]
        if not parts:
            return None

        base_price = next((l.bsi_base_price for l in lengths if l.bsi_base_price), 2999)
        total = (base_price + (length_rec.bsi_surcharge or 0) + (shade_rec.bsi_surcharge or 0)
                 + (finish_rec.bsi_surcharge or 0))
        summary = ' · '.join(parts)
        return {
            'summary': summary,
            'total': total,
            'vals': {
                'name': summary,
                'bsi_category': 'hair',
                # Keeps it out of the website's own Services list and the main
                # Services catalog menu (see their own domains).
                'bsi_is_custom_look': True,
                'bsi_look_length_id': length_rec.id if length_rec else False,
                'bsi_look_shade_id': shade_rec.id if shade_rec else False,
                'bsi_look_finish_id': finish_rec.id if finish_rec else False,
                'bsi_price': '₹%d' % int(total),
                'bsi_price_amount': total,
            },
        }

    def _bsi_resolve_colour_lab(self, colour_lab):
        """The Colour Lab plan behind a "Book a colour consultation" booking, resolved to
        the one service that prices it -- the Design-Your-Look pattern (_bsi_resolve_look).

        Only the visitor's four raw picks are read from the request -- from/to level
        (the swatch numbers, 1-based positions in LEVELS), tone key and hair-condition
        key -- and the plan is recomputed here with the exact maths of the page's own
        labPlan() over the exact records the page was built from
        (bsi.enrich.data._bsi_colour_lab: LEVELS/TONES/CONDITIONS/BSI_LAB_PRICING). Any
        price, label or duration the page sends is ignored, so the booking is charged
        the salon's own figure. Returns None when the picks do not name a plan.
        """
        if not isinstance(colour_lab, dict):
            return None
        levels, tones, conditions, pricing = request.env['bsi.enrich.data'].sudo()._bsi_colour_lab()
        if not levels or not tones or not conditions:
            return None

        def level_index(key):
            raw = colour_lab.get(key)
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return None
            return value if 1 <= value <= len(levels) else None

        lab_from, lab_to = level_index('lab_from'), level_index('lab_to')
        if lab_from is None or lab_to is None:
            return None
        start, target = levels[lab_from - 1], levels[lab_to - 1]
        # labPlan(): an unknown tone/condition falls back to the first one listed.
        tone = next((t for t in tones if t['id'] == colour_lab.get('lab_tone')), tones[0])
        cond = next((c for c in conditions if c['id'] == colour_lab.get('lab_condition')), conditions[0])

        lift = lab_to - lab_from               # + = lighter, - = darker
        going_darker = lift < 0
        per_session = max(1, int(cond['maxLift'] or 0))
        sessions = 1 if going_darker else max(1, int(math.ceil(lift / float(per_session))))
        price = ((pricing['baseDarker'] if going_darker else pricing['baseLighter'])
                 + max(0, lift) * pricing['perLevel']
                 + (sessions - 1) * pricing['perExtraSession'] + tone['toner'])
        minutes = ((pricing['minutesDarker'] if going_darker else pricing['minutesLighter'])
                   + max(0, lift) * pricing['minutesPerLevel']
                   + (pricing['minutesToner'] if tone['toner'] else 0))

        from_label = 'Level %s %s' % (start['level'], start['name'])
        to_label = 'Level %s %s' % (target['level'], target['name'])
        name = 'Colour consultation · %s → %s · %s' % (from_label, to_label, tone['name'])
        hours, mins = divmod(int(minutes), 60)
        chair_time = '%dh%s' % (hours, ' %dm' % mins if mins else '') if hours else '%dm' % mins
        session_label = '%d session%s' % (sessions, '' if sessions == 1 else 's')
        brief = '%s → %s, tone: %s, hair condition: %s, %s, %s chair time' % (
            from_label, to_label, tone['name'], cond['name'], session_label, chair_time)
        return {
            'name': name,
            'price': price,
            'minutes': int(minutes),
            'sessions': sessions,
            'from': from_label, 'to': to_label, 'tone': tone['name'], 'condition': cond['name'],
            # The lead's notes line -- the colourist's starting point, built from the
            # resolved records rather than any text the page sent.
            'note': 'Colour consultation from the Colour Lab: %s — estimated ₹%s.'
                    % (brief, '{:,}'.format(int(price))),
            'vals': {
                'name': name,
                'bsi_category': 'colour',
                # One per booking, like a Design-Your-Look service: kept out of the
                # website's Services list and the Services catalog menu.
                'bsi_is_custom_look': True,
                'bsi_description': 'Booked from the website Colour Lab: %s.' % brief,
                'bsi_price': '₹{:,}'.format(int(price)),
                'bsi_price_amount': price,
                'bsi_duration': '%d min' % int(minutes),
            },
        }

    @staticmethod
    def _bsi_parse_custom_time(label):
        """'10:45 AM' / '7:05 pm' / '19:30' -> hours as a float (10.75), or None."""
        match = re.match(r'^\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])?\.?\s*[Mm]?\.?\s*$', str(label or ''))
        if not match:
            return None
        hours, minutes = int(match.group(1)), int(match.group(2) or 0)
        meridiem = (match.group(3) or '').lower()
        if meridiem:
            if not 1 <= hours <= 12:
                return None
            hours = hours % 12 + (12 if meridiem == 'p' else 0)
        if hours > 23 or minutes > 59:
            return None
        return round(hours + minutes / 60.0, 4)

    def _bsi_resolve_selection(self, location=None, city_name=None, store_name=None,
                               slot_label=None, chair_numbers=None, package_id=None,
                               selected_service_id=None, selected_service_ids=None,
                               reward_service_id=None, look_length=None, look_shade_index=None,
                               look_finish=None, addon_keys=None, artist_id=None,
                               colour_lab=None, create_look=False, offer_id=None):
        """Everything a booking request names, resolved to real records once.

        Shared by /salon/api/booking and /salon/api/booking_quote so the two can
        never disagree about what was selected or what it costs. `create_look`
        is the single difference between them: a real booking persists the
        Design-Your-Look service, a quote only instantiates it.
        """
        Service = request.env['bsi.salon.service'].sudo()
        reward_service = Service.browse(
            int(reward_service_id) if str(reward_service_id or '').isdigit() else 0).exists()
        selected_service = Service.browse(
            int(selected_service_id) if str(selected_service_id or '').isdigit() else 0).exists()
        selected_services = Service.browse(
            [int(i) for i in (selected_service_ids or []) if str(i).isdigit()]).exists()
        package = request.env['bsi.salon.package'].sudo().browse(
            int(package_id) if str(package_id or '').isdigit() else 0).exists()
        artist = request.env['bsi.salon.team.member'].sudo().browse(
            int(artist_id) if str(artist_id or '').isdigit() else 0).exists()

        # Services-menu "Book offer" cards (see bsi_salon_web/controllers/enrich_offers.py
        # and bsi.salon.offer): the id is re-resolved and re-validated here, every time --
        # the website's own BSI_OFFERS only ever listed bookable offers when the page was
        # built, which may be stale (offer edited/archived/expired since), and nothing
        # about its price is ever trusted from the client in the first place.
        offer = request.env['bsi.salon.offer'].sudo().browse(
            int(offer_id) if str(offer_id or '').isdigit() else 0).exists()
        offer_error = ''
        if offer and not offer._bsi_is_bookable():
            offer_error = 'This offer is no longer available.'
            offer = request.env['bsi.salon.offer']

        slot = request.env['bsi.salon.time.slot']
        custom_time = None
        if slot_label:
            _labels, lookup = request.env['bsi.enrich.data'].sudo()._bsi_time_slots()
            slot_id = lookup.get(str(slot_label).strip())
            if slot_id:
                slot = slot.sudo().browse(slot_id)
            else:
                # PHASE 8 DEV -- not one of the fixed slots: the visitor picked an exact
                # time on the Time step ("10:45 AM"). It used to survive only as a line
                # in the notes, so CRM showed the lead with no time at all; it is now
                # stored as the lead's own Custom Time (bsi_use_slot False +
                # bsi_preferred_time), exactly what staff enter for a custom booking.
                custom_time = self._bsi_parse_custom_time(slot_label)

        chair_ids = [int(c) for c in (chair_numbers or []) if str(c).isdigit()]
        chairs = request.env['bsi.salon.chair'].sudo().browse(chair_ids).exists()
        if location and chairs and any(c.bsi_location_id != location for c in chairs):
            chairs = request.env['bsi.salon.chair']  # stale/mismatched page -- notes only

        notes = ['Booked from the Enrich website.']
        if store_name or city_name:
            notes.append('Branch: %s%s' % (store_name or '', ' (%s)' % city_name if city_name else ''))
        if slot_label:
            notes.append('Requested time: %s' % slot_label)
        if chairs:
            notes.append('Chair preference: %s' % ', '.join(chairs.mapped('name')))
        elif chair_ids:
            notes.append('Chair preference: %s' % ', '.join(str(c) for c in chair_ids))

        # reward_service_id used to carry a discount worth the service's points, on the
        # word of the page alone (the points were meant to have been spent beforehand
        # through /salon/api/loyalty_redeem) -- anyone could send it and get the discount
        # without spending anything. Points now only ever come off a booking through
        # _bsi_booking_quote, which checks the balance and spends them on confirmation,
        # so a reward_service_id is just one more selected service.
        loyalty_redeemed_amount = 0.0

        addons = request.env['bsi.salon.addon']
        if addon_keys:
            keys = [str(k).strip() for k in addon_keys if str(k or '').strip()]
            if keys:
                addons = request.env['bsi.salon.addon'].sudo().search([('bsi_key', 'in', keys)])
                if addons:
                    notes.append('Chair-side add-ons: %s' % ', '.join(addons.mapped('name')))

        # A package is exclusive with individual services on the mixin
        # (_bsi_check_package_exclusive_common requires bsi_service_ids to
        # exactly equal the package's own) -- when one is present, its own
        # services always win and nothing else (reward/selected/look) is
        # unioned in, regardless of what else the request happens to carry.
        # An offer is the same shape (see _bsi_check_offer_exclusive_common) -- a
        # package takes priority if a request somehow names both.
        if package:
            services = package.bsi_service_ids
            notes.append('Package selected on the site: %s' % package.name)
            offer = request.env['bsi.salon.offer']
        elif offer:
            services = offer.bsi_service_ids
            notes.append('Offer selected on the site: %s' % offer.name)
        else:
            services = reward_service
            if selected_service:
                services |= selected_service
                notes.append('Service selected on the site: %s' % selected_service.name)
            if selected_services:
                services |= selected_services
                notes.append('Services selected on the site: %s'
                             % ', '.join(selected_services.mapped('name')))

        look = None
        if not package and not offer and (look_length or look_finish or look_shade_index is not None):
            look = self._bsi_resolve_look(look_length, look_shade_index, look_finish)
        if look:
            # A real bsi.salon.service, one per booking, rather than a pair of plain
            # fields on the lead -- so this booking's Services/Services Amount/Total
            # Amount populate exactly the way a normal service-based booking's do, and
            # the length/shade/finish behind the number are one click away on the
            # service's own form.
            look_service = Service.create(look['vals']) if create_look else Service.new(look['vals'])
            services |= look_service
            notes.append('Look configured on the site: %s — estimated ₹%d'
                         % (look['summary'], int(look['total'])))

        colour = None
        if not package and not offer and not look and colour_lab:
            colour = self._bsi_resolve_colour_lab(colour_lab)
        if colour:
            # "Book a colour consultation" from the Colour Lab: the consultation for the
            # exact plan configured there IS the booking's service (it used to preselect
            # an unrelated catalogue colour service instead), priced server-side.
            colour_service = Service.create(colour['vals']) if create_look else Service.new(colour['vals'])
            services |= colour_service
            notes.append(colour['note'])

        return {
            'services': services, 'package': package, 'addons': addons, 'artist': artist,
            'chairs': chairs, 'slot': slot, 'custom_time': custom_time, 'look': look,
            'colour_lab': colour, 'notes': notes,
            'reward_service': reward_service,
            'reward_redeemed_amount': loyalty_redeemed_amount,
            'offer': offer, 'offer_error': offer_error,
        }

    def _bsi_quote_lead(self, selection, partner, loyalty_amount=0.0,
                        gift_card=None, gift_amount=0.0, promo=None):
        """An unsaved crm.lead carrying this selection, priced by the mixin itself.

        Nothing here re-implements the pricing: bsi_services_amount,
        bsi_discount_percent, bsi_gift_card_applied_amount and bsi_amount_total are
        all read straight off bsi.salon.booking.mixin._bsi_compute_bsi_amounts_common,
        so the figure the site shows is the figure the salon would compute.
        """
        lead = request.env['crm.lead'].sudo().new({
            'name': 'Enrich website quote',
            'type': 'opportunity',
            'partner_id': partner.id if partner else False,
            'contact_name': partner.name if partner else False,
            'email_from': partner.email if partner else False,
            'phone': partner.phone if partner else False,
        })
        if selection['services']:
            lead.bsi_service_ids = selection['services']
        if selection['package']:
            lead.bsi_package_id = selection['package'].id
        if selection.get('offer'):
            lead.bsi_offer_id = selection['offer'].id
        if selection['addons']:
            lead.bsi_addon_ids = selection['addons']
        if selection['artist']:
            lead.bsi_artist_id = selection['artist'].id
        # Derived here, never taken from the request: the site sends whatever its own
        # membership banner says, and the discount must follow the real subscription
        # (which the mixin checks again anyway -- see _bsi_compute_bsi_amounts_common's
        # own _bsi_find_active_subscriptions call).
        lead.bsi_is_member = bool(lead._bsi_find_active_subscriptions())
        lead.bsi_loyalty_redeemed_amount = float(loyalty_amount or 0.0)
        if promo and promo['reward']:
            # The mixin works out what it takes off (bsi_promo_discount_amount).
            lead.bsi_promo_code = promo['code']
            lead.bsi_promo_reward_id = promo['reward'].id
            lead.bsi_promo_coupon_id = promo['coupon'].id if promo['coupon'] else False
        if gift_card:
            lead.bsi_use_gift_card = True
            lead.bsi_gift_card_id = gift_card.id
            lead.bsi_gift_card_redeem_amount = float(gift_amount or 0.0)
        return lead

    def _bsi_redeemable_base(self, lead, selection):
        """What a points redemption is measured against -- the booking subtotal.

        bsi_services_amount is the mixin's own undiscounted services figure (already
        the package's flat price when one is applied); the artist surcharge and the
        add-ons are the only two other things in the subtotal it discounts from (see
        _bsi_compute_bsi_amounts_common), and a package (or an offer, same shape)
        suppresses the artist surcharge exactly as it does there.
        """
        artist_amount = 0.0 if (selection['package'] or selection.get('offer')) else (
            selection['artist'].bsi_charge_amount or 0.0 if selection['artist'] else 0.0)
        addons_amount = sum(selection['addons'].mapped('bsi_price')) if selection['addons'] else 0.0
        return (lead.bsi_services_amount or 0.0) + artist_amount + addons_amount

    def _bsi_resolve_gift_card(self, lead, code):
        """The card this code names, if it can actually be redeemed.

        Eligibility is bsi.salon.booking.mixin._bsi_find_gift_card_by_code's own answer,
        not a second opinion -- the same rule the backend's Gift Card constraint
        accepts, so a card the site lets a customer apply is always a card the lead
        will accept. A gift card is a bearer card (as in Odoo's own cart): a card
        someone was given usually carries no customer, or the buyer's. Returns
        (card, error).
        """
        code = (code or '').strip()
        if not code:
            return request.env['loyalty.card'], False

        card = lead._bsi_find_gift_card_by_code(code)
        if card:
            return card, False

        # Nothing usable matched -- say which reason it was, rather than a flat
        # "invalid code" that a customer cannot act on.
        raw = request.env['loyalty.card'].sudo().search(
            [('code', '=ilike', escape_psql(code)),
             ('program_id.program_type', '=', 'gift_card')], limit=1)
        empty = request.env['loyalty.card']
        if not raw:
            return empty, 'We could not find a gift card with that code.'
        today = fields.Date.context_today(request)
        if raw.expiration_date and raw.expiration_date < today:
            return empty, 'Gift card %s expired on %s.' % (raw.code, raw.expiration_date)
        if raw.points <= 0:
            return empty, 'Gift card %s has no balance left.' % raw.code
        return empty, 'Gift card %s can no longer be used.' % raw.code

    def _bsi_payment_features(self):
        """Which redemptions the salon offers on the website at all.

        The same two Settings toggles that hide the Loyalty Wallet and Gift Cards
        sections (bsi_salon_backend.show_loyalty_points / show_gift_card) switch the
        Confirm screen's redemptions off too -- and are enforced here, not only in
        the page, so a switched-off redemption cannot be requested by hand.
        """
        ICP = request.env['ir.config_parameter'].sudo()
        return {
            'loyalty': ICP.get_param('bsi_salon_backend.show_loyalty_points', 'True') == 'True',
            'gift_card': ICP.get_param('bsi_salon_backend.show_gift_card', 'True') == 'True',
            'membership': ICP.get_param('bsi_salon_backend.show_membership', 'True') == 'True',
        }

    def _bsi_resolve_reward(self, params, partner, balance, features):
        """The loyalty reward the customer picked for this booking, if they may use it.

        Returns (reward, error): an empty recordset plus a customer-facing reason when
        the pick cannot be honoured (signed out, not enough points, archived, or a
        free service asked for on a package booking).
        """
        Reward = request.env['loyalty.reward'].sudo()
        raw = params.get('reward_id')
        if not features['loyalty'] or not str(raw or '').isdigit():
            return Reward, ''
        # Only active rewards from the Salon Loyalty Points program can be used.
        reward = Reward.browse(int(raw)).exists().filtered(lambda r: r.active)
        if not reward:
            return Reward, 'That reward is no longer available.'
        if not partner:
            return Reward, 'Sign in to use your loyalty rewards.'
        if balance < reward.required_points:
            return Reward, '%s needs %d points; you have %d (%d more needed).' % (
                reward.description or reward.display_name,
                int(reward.required_points), balance,
                int(reward.required_points) - balance)
        if reward.reward_type == 'product' and not reward.reward_product_ids:
            return Reward, 'That reward is no longer available.'
        if reward.reward_type == 'product' and params.get('package_id'):
            return Reward, 'A free-product reward cannot be added to a package booking.'
        return reward, ''

    def _bsi_booking_quote(self, params, partner):
        """The one priced answer both the quote endpoint and the real booking use.

        auto_loyalty / auto_gift_card ask the quote to pick the redemption itself:
        the most points the rules allow on this booking, and the customer's own
        usable gift card. The page sends them until the customer changes either
        one by hand, then sends back exactly what the quote chose -- so the real
        booking (which never sends the auto flags) is priced on the same figures.
        """
        features = self._bsi_payment_features()
        loyalty_points = params.get('loyalty_points') if features['loyalty'] else 0
        gift_card_code = params.get('gift_card_code') if features['gift_card'] else ''
        promo_code = str(params.get('promo_code') or '').strip()
        auto_loyalty = bool(params.get('auto_loyalty')) and features['loyalty'] and bool(partner)
        auto_gift = bool(params.get('auto_gift_card')) and features['gift_card'] and bool(partner)
        location = params.get('location')

        # entered_code: whatever the customer just typed into the Confirm step's code box
        # -- a gift card (it pays) or a discount / promo / coupon code (it discounts),
        # told apart here, so one box takes any code. It replaces the current gift card
        # or discount code of its own kind; everything else stays as it was.
        Lead = request.env['crm.lead'].sudo()
        entered_code = str(params.get('entered_code') or '').strip()
        entry = {'kind': '', 'error': ''}
        if entered_code and features['gift_card'] and Lead._bsi_find_gift_card_by_code(entered_code):
            gift_card_code, auto_gift, entry['kind'] = entered_code, False, 'gift_card'
        elif entered_code:
            found = Lead._bsi_resolve_promo_code(entered_code)
            if found['reward']:
                promo_code, entry['kind'] = entered_code, 'promo'
            elif not found['not_found']:
                entry['error'] = found['error']
            elif features['gift_card'] and request.env['loyalty.card'].sudo().search_count(
                    [('code', '=ilike', escape_psql(entered_code)), ('program_id.program_type', '=', 'gift_card')]):
                entry['error'] = self._bsi_resolve_gift_card(Lead, entered_code)[1]
            else:
                entry['error'] = 'We could not find a gift card or discount code "%s".' % entered_code

        # PHASE 9 DEV -- a loyalty reward picked on the Confirm step (e.g. 50 points =
        # 1 free Hair Spa). Checked against the balance here; the points are only spent
        # when /salon/api/booking records the booking.
        balance = partner.bsi_loyalty_points if partner else 0
        reward, reward_error = self._bsi_resolve_reward(params, partner, balance, features)
        selected_ids = [int(i) for i in (params.get('selected_service_ids') or []) if str(i).isdigit()]
        if reward and reward.reward_type == 'product' and reward.reward_product_ids:
            # For product rewards, no service pre-selection needed in our flow.
            single = params.get('selected_service_id')
            if not selected_ids and str(single or '').isdigit():
                selected_ids = [int(single)]

        selection = self._bsi_resolve_selection(
            location=location,
            city_name=params.get('city_name'), store_name=params.get('store_name'),
            slot_label=params.get('slot_label'), chair_numbers=params.get('chair_numbers'),
            package_id=params.get('package_id'),
            selected_service_id=params.get('selected_service_id'),
            selected_service_ids=selected_ids,
            reward_service_id=params.get('reward_service_id'),
            look_length=params.get('look_length'),
            look_shade_index=params.get('look_shade_index'),
            look_finish=params.get('look_finish'),
            addon_keys=params.get('addon_keys'),
            artist_id=params.get('artist_id'),
            colour_lab=params.get('colour_lab'),
            create_look=bool(params.get('create_look')),
            offer_id=params.get('offer_id'),
        )

        # Priced once with no redemption, to learn the base the loyalty cap and the
        # gift card are measured against, then once more with whatever survived
        # validation. Two passes rather than one because the redemption rules depend
        # on the very subtotal the first pass computes.
        base_lead = self._bsi_quote_lead(selection, partner)
        redeemable_base = self._bsi_redeemable_base(base_lead, selection)

        Loyalty = request.env['loyalty.card'].sudo()
        rules = Loyalty._bsi_get_redemption_rules()

        # Reward first, then the points of any booked service that carries its own
        # Loyalty Points (used automatically while the balance covers them), then --
        # from whatever balance is left -- a free points redemption.
        remaining = balance
        reward_amount = 0.0
        if reward:
            reward_amount = reward._bsi_value_on(redeemable_base)
            remaining -= reward.required_points
        use_service_points = params.get('use_service_points') is not False
        # points_service_ids: the services the customer chose to pay for with their own
        # points ("Book · use N pts", or "Use N pts" on the Confirm step). When the page
        # sends it, only those are applied; without it (older pages) every eligible
        # service is, as before, while use_service_points allows.
        raw_points_ids = params.get('points_service_ids')
        chosen_points_ids = None if raw_points_ids is None else {
            int(i) for i in (raw_points_ids or []) if str(i).isdigit()}
        service_points = []
        if features['loyalty'] and partner and not selection['package']:
            free_services = request.env['bsi.salon.service']
            for service in selection['services'].sorted('id'):
                points_needed = service.bsi_loyalty_points or 0
                # Only services switched on for points on the website, and never one a
                # reward on this booking already makes free.
                if points_needed <= 0 or service in free_services \
                        or not service._bsi_points_on_website():
                    continue
                price = service._bsi_get_effective_price() or 0.0
                amount = min(points_needed * rules['point_value'], price)
                if rules['point_value'] and points_needed * rules['point_value'] > price:
                    # Never spend more points than the service is worth.
                    points_needed = int(math.ceil(price / rules['point_value']))
                selected = use_service_points if chosen_points_ids is None \
                    else service.id in chosen_points_ids
                applied = bool(selected and amount > 0 and remaining >= points_needed)
                if applied:
                    remaining -= points_needed
                service_points.append({'service': service, 'points': points_needed,
                                       'amount': amount, 'applied': applied,
                                       'selected': bool(selected)})
        service_points_amount = sum(e['amount'] for e in service_points if e['applied'])
        service_points_used = sum(e['points'] for e in service_points if e['applied'])
        free_base = max(0.0, redeemable_base - reward_amount - service_points_amount)

        cap_amount = free_base * rules['max_percent'] / 100.0
        max_points = int(cap_amount // rules['point_value']) if rules['point_value'] else 0
        usable_points = min(max_points, remaining)
        # "Redeemable" means the rules would accept at least the minimum block here.
        redeemable = bool(features['loyalty'] and partner
                          and usable_points >= rules['min_points'] and usable_points > 0)
        if auto_loyalty:
            loyalty_points = usable_points if redeemable else 0
        loyalty = Loyalty._bsi_quote_points_redemption(partner, loyalty_points, free_base, balance=remaining)
        if auto_loyalty and loyalty['error']:
            # An automatic pick is never shown as a refusal -- it just is not applied.
            loyalty = Loyalty._bsi_quote_points_redemption(partner, 0, free_base, balance=remaining)
        points_discount = reward_amount + service_points_amount + selection['reward_redeemed_amount']

        # The customer's own best card: soonest to expire first, so the balance that
        # would otherwise lapse is the one spent.
        own_cards = base_lead._bsi_find_active_gift_card() if (
            partner and features['gift_card']) else request.env['loyalty.card']
        own_card = own_cards.sorted(
            lambda c: (c.expiration_date or fields.Date.to_date('9999-12-31'), -c.points))[:1]
        if auto_gift:
            gift_card_code = own_card.code if own_card else ''

        gift_card, gift_error = self._bsi_resolve_gift_card(base_lead, gift_card_code)
        # Offer the whole balance: the mixin clamps what is actually applied to what
        # is still owed after every other discount (see bsi_gift_card_applied_amount),
        # so asking for more than the booking needs can never overdraw the card.
        gift_request = gift_card.points if gift_card else 0.0

        # The discount code: validated by the mixin (program dates, usage limit, coupon
        # used / expired, discount rewards only), then priced by it on the lead below.
        no_promo = {'code': '', 'reward': request.env['loyalty.reward'],
                    'coupon': request.env['loyalty.card']}
        promo, promo_error = no_promo, ''
        if promo_code:
            found = base_lead._bsi_resolve_promo_code(promo_code)
            if found['reward'] and found['minimum'] and redeemable_base < found['minimum']:
                promo_error = 'Spend ₹%s or more to use the code "%s".' % (
                    '{:,.0f}'.format(found['minimum']), found['code'])
            elif found['reward']:
                promo = found
            else:
                promo_error = found['error']

        lead = self._bsi_quote_lead(
            selection, partner,
            loyalty_amount=loyalty['amount'] + points_discount,
            gift_card=gift_card or None, gift_amount=gift_request, promo=promo)
        if promo['reward'] and not (lead.bsi_promo_discount_amount or 0.0):
            # e.g. a discount on products none of these services are, or nothing left
            # to take off -- refused rather than shown as applied for ₹0.
            promo_error = 'The code "%s" gives no discount on this booking.' % promo['code']
            promo = no_promo
            lead = self._bsi_quote_lead(
                selection, partner,
                loyalty_amount=loyalty['amount'] + points_discount,
                gift_card=gift_card or None, gift_amount=gift_request)
        if entry['kind'] == 'promo' and promo_error:
            entry['error'] = promo_error
        if auto_gift and gift_card and not (lead.bsi_gift_card_applied_amount or 0.0):
            # Points already cover everything the card could -- leave the card untouched.
            gift_card = request.env['loyalty.card']
            lead = self._bsi_quote_lead(
                selection, partner,
                loyalty_amount=loyalty['amount'] + points_discount, promo=promo)
        all_rewards = request.env['loyalty.reward'].sudo().search(
            [('program_id.name', '=', 'Salon Loyalty Points')]) if features['loyalty'] \
            else request.env['loyalty.reward']
        # Every point this booking takes off the balance once confirmed: the reward, the
        # service points and any free points redemption.
        points_after = remaining - (loyalty['points'] or 0)
        return {
            'selection': selection,
            'lead': lead,
            'loyalty': loyalty,
            'reward': reward,
            'reward_error': reward_error,
            'reward_amount': reward_amount,
            'service_points': service_points,
            'gift_card': gift_card,
            'gift_card_error': gift_error,
            'promo': promo,
            'promo_error': promo_error,
            'payload': {
                'ok': True,
                'currency': '₹',
                'logged_in': bool(partner),
                'features': features,
                'services_amount': round(lead.bsi_services_amount or 0.0, 2),
                # The Colour Lab consultation as the server priced it -- the Confirm
                # screen's consultation line shows this, not the page's own estimate.
                'colour_lab': {
                    'name': selection['colour_lab']['name'],
                    'price': round(selection['colour_lab']['price'], 2),
                    'minutes': selection['colour_lab']['minutes'],
                    'sessions': selection['colour_lab']['sessions'],
                } if selection['colour_lab'] else None,
                # Services-menu offer (see bsi.salon.offer / enrich_offers.py) -- the
                # Confirm screen's "Services" line already shows services_amount above at
                # the offer's own price (bsi.salon.booking.mixin's amounts compute prices
                # an offer booking the same way it prices a package), this is just enough
                # for the page to label it and show an "offer no longer available" error.
                'offer': {
                    'id': selection['offer'].id if selection['offer'] else None,
                    'name': selection['offer'].name if selection['offer'] else '',
                    'badge': selection['offer'].bsi_badge if selection['offer'] else '',
                    'error': selection['offer_error'],
                },
                'subtotal': round(redeemable_base, 2),
                'membership': {
                    'active': bool(lead.bsi_is_member and lead.bsi_discount_percent),
                    'tier': lead.bsi_membership_id.name or '',
                    'percent': lead.bsi_discount_percent or 0.0,
                },
                'reward_amount': round(selection['reward_redeemed_amount'], 2),
                'rewards': [{
                    'id': r.id,
                    'name': r.description or r.display_name or '',
                    'cost': int(r.required_points),
                    'benefit': ('%s%% off' % int(r.discount) if r.discount_mode == 'percent'
                                else '₹%s off' % int(r.discount)) if r.reward_type == 'discount'
                               else ', '.join(r.reward_product_ids.mapped('name')) or '',
                    'type': r.reward_type,
                    'service_id': None,
                    'service_ids': [],
                    'service_names': [],
                    'affordable': bool(partner) and balance >= r.required_points,
                    'needed': max(0, int(r.required_points) - balance) if partner else int(r.required_points),
                    'applied': bool(reward) and r == reward,
                } for r in all_rewards],
                'reward': {
                    'id': reward.id if reward else None,
                    'name': (reward.description or reward.display_name or '') if reward else '',
                    'benefit': ('%s%% off' % int(reward.discount)
                                if reward and reward.discount_mode == 'percent'
                                else '₹%s off' % int(reward.discount or 0)) if reward else '',
                    'points': int(reward.required_points) if reward else 0,
                    'amount': round(reward_amount, 2),
                    'service_ids': [],
                    'error': reward_error or '',
                },
                'service_points': {
                    'enabled': use_service_points,
                    'points': service_points_used,
                    'amount': round(service_points_amount, 2),
                    'lines': [{
                        'id': e['service'].id, 'name': e['service'].name, 'points': e['points'],
                        'amount': round(e['amount'], 2), 'applied': e['applied'],
                        'selected': e['selected'],
                    } for e in service_points],
                },
                'loyalty': {
                    'remaining': remaining,
                    'balance': balance,
                    # What the balance will be once this booking is confirmed, and how
                    # many points it uses in total -- the page shows these as the
                    # customer's available points.
                    'available': points_after,
                    'used': balance - points_after,
                    'points': loyalty['points'],
                    'amount': round(loyalty['amount'], 2),
                    'error': loyalty['error'] or '',
                    'point_value': rules['point_value'],
                    'min_points': rules['min_points'],
                    'max_percent': rules['max_percent'],
                    'max_points': usable_points,
                    'redeemable': redeemable,
                    'auto': auto_loyalty,
                },
                'gift_card': {
                    'auto': auto_gift,
                    'own_code': own_card.code if own_card else '',
                    'own_balance': round(own_card.points, 2) if own_card else 0.0,
                    'code': gift_card.code if gift_card else '',
                    'balance': round(gift_card.points, 2) if gift_card else 0.0,
                    'expiry': gift_card.expiration_date.isoformat()
                              if gift_card and gift_card.expiration_date else '',
                    'applied': round(lead.bsi_gift_card_applied_amount or 0.0, 2),
                    # The code box's own message too: a code just typed that is neither
                    # a usable gift card nor a usable discount code says why here.
                    'error': gift_error or entry['error'] or '',
                },
                'promo': {
                    'code': promo['code'] if promo['reward'] else '',
                    # The program's own name (what the salon called it), not the reward's
                    # auto-description, which is written in the company currency.
                    'name': (promo['reward'].program_id.name or promo['reward'].description or '')
                            if promo['reward'] else '',
                    'amount': round(lead.bsi_promo_discount_amount or 0.0, 2),
                    'error': promo_error or '',
                },
                'code_entry': {'kind': entry['kind'], 'error': entry['error']},
                'amount_total': round(lead.bsi_amount_total or 0.0, 2),
            },
        }

    @http.route('/salon/api/booking_quote', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_booking_quote(self, **kwargs):
        """Price a booking-in-progress, including any redemption, without saving anything.

        Every number on the Confirm screen's payment panel comes from here. Nothing is
        written: the loyalty balance is only really spent, and the gift card only really
        attached, when /salon/api/booking below runs the exact same resolution again.
        """
        user = request.env.user
        partner = user.partner_id if not user._is_public() else request.env['res.partner']
        try:
            quote = self._bsi_booking_quote(dict(kwargs, location=self._bsi_location_of(kwargs)), partner)
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: booking could not be quoted')
            return {'ok': False}
        return quote['payload']

    def _bsi_location_of(self, params):
        raw = params.get('location_id')
        return request.env['bsi.salon.location'].sudo().browse(
            int(raw) if str(raw or '').isdigit() else 0).exists()

    @http.route('/salon/api/gift_card_validate', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_gift_card_validate(self, code=None, **kwargs):
        """Check one gift card code for the signed-in customer, before any booking exists.

        Same eligibility answer the Confirm screen's own quote gives (see
        _bsi_resolve_gift_card) -- this just lets the card be checked the moment it is
        typed, rather than only once the whole selection is priced.
        """
        user = request.env.user
        if user._is_public():
            return {'ok': False, 'error': 'Sign in to pay with a gift card.'}
        partner = user.partner_id
        probe = request.env['crm.lead'].sudo().new({
            'name': 'Enrich gift card check', 'type': 'opportunity',
            'partner_id': partner.id, 'email_from': partner.email, 'phone': partner.phone,
        })
        card, error = self._bsi_resolve_gift_card(probe, code)
        if not card:
            return {'ok': False, 'error': error or 'Enter a gift card code.'}
        return {
            'ok': True,
            'code': card.code,
            'balance': round(card.points, 2),
            'expiry': card.expiration_date.isoformat() if card.expiration_date else '',
        }

    @http.route('/salon/api/booking', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_booking(self, location_id=None, slot_label=None, chair_numbers=None,
                              is_member=False, city_name=None, store_name=None,
                              reward_service_id=None, artist_id=None, look_length=None,
                              look_shade_index=None, look_finish=None, addon_keys=None,
                              selected_service_id=None, selected_service_ids=None,
                              package_id=None, loyalty_points=None, gift_card_code=None,
                              preferred_date=None, reward_id=None, use_service_points=None,
                              colour_lab=None, **kwargs):
        """Record a booking request from the site as a CRM lead.

        A lead rather than an appointment, which is the route the salon's own
        booking form took as well: staff review it and the appointment is built
        when the lead is marked Won.

        What every selection parameter means, and why each is trusted or not, now
        lives with the resolution itself in _bsi_resolve_selection above -- this
        method is the part that actually writes, plus the two redemptions, which
        cannot be resolved without writing.

        loyalty_points and gift_card_code are re-validated here through the exact
        same _bsi_booking_quote the Confirm screen's own figures came from, so the
        discount recorded on the lead is the discount the customer was shown and
        neither can be inflated by a crafted request. The points are spent for real
        in this same transaction (a rejected booking rolls the spend back with it);
        the gift card balance is spent later, the moment this lead is marked Won,
        which is where bsi_salon_backend already moves it (see
        crm.lead._bsi_create_appointment_from_lead).

        A signed-in customer's own contact details are read off request.env.user
        rather than left for staff to ask -- a guest checkout still has nothing
        to read (auth='public' means user._is_public() then), same guard
        membership_status/customer_city already use for the same reason.
        """
        user = request.env.user
        partner = user.partner_id if not user._is_public() else request.env['res.partner']
        location = request.env['bsi.salon.location'].sudo().browse(
            int(location_id) if str(location_id or '').isdigit() else 0).exists()
        booking_date, date_error = self._bsi_parse_booking_date(preferred_date)
        if date_error:
            return {'ok': False, 'error': date_error}
        # Everything needed to actually reach the customer and seat them -- checked
        # here as well as on the page (never trust the client). See
        # enrich_confirm.resolve_contact for the contact rules.
        if not location:
            return {'ok': False, 'error': 'Please choose a branch for your appointment.'}
        # A time (like a chair) is optional: without one the lead is recorded with no
        # slot and staff confirm a time with the customer before marking it Won.
        contact, contact_errors = enrich_confirm.resolve_contact(partner, kwargs)
        if contact_errors:
            return {'ok': False, 'fields': contact_errors,
                    'error': next(iter(contact_errors.values()))}

        params = {
            'location': location, 'location_id': location_id,
            'city_name': city_name, 'store_name': store_name, 'slot_label': slot_label,
            'chair_numbers': chair_numbers, 'package_id': package_id,
            'selected_service_id': selected_service_id,
            'selected_service_ids': selected_service_ids,
            'reward_service_id': reward_service_id, 'look_length': look_length,
            'look_shade_index': look_shade_index, 'look_finish': look_finish,
            'addon_keys': addon_keys, 'artist_id': artist_id,
            'loyalty_points': loyalty_points, 'gift_card_code': gift_card_code,
            'reward_id': reward_id, 'use_service_points': use_service_points,
            # The services the customer chose to pay with points (see _bsi_booking_quote).
            'points_service_ids': kwargs.get('points_service_ids'),
            # The discount / promo / coupon code the Confirm step applied.
            'promo_code': kwargs.get('promo_code'),
            'colour_lab': colour_lab,
            'create_look': True,
            # Services-menu "Book offer" (see bsi_salon_web/controllers/enrich_offers.py) --
            # re-validated below, never trusted just because the page sent it.
            'offer_id': kwargs.get('offer_id'),
        }

        try:
            quote = self._bsi_booking_quote(params, partner)
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: booking request could not be priced')
            return {'ok': False}

        selection = quote['selection']
        # An offer that was requested but failed re-validation (expired, unpublished,
        # archived since the page was built) never silently books as a plain service
        # selection -- the customer is told, same as any other refused redemption above.
        if kwargs.get('offer_id') and selection['offer_error']:
            request.env.cr.rollback()
            return {'ok': False, 'error': selection['offer_error']}
        if not selection['services'] and not selection['package'] and not selection['offer']:
            request.env.cr.rollback()
            return {'ok': False, 'error': 'Please add at least one service to your booking.'}
        # Only a time that was sent but cannot be read is refused; none at all is fine.
        if str(slot_label or '').strip() and not selection['slot'] and selection['custom_time'] is None:
            request.env.cr.rollback()
            return {'ok': False, 'error': 'Please choose a valid time for your appointment.'}
        loyalty = quote['loyalty']
        gift_card = quote['gift_card']
        # A redemption the rules refused is reported instead of quietly dropped: the
        # customer is about to be charged the un-discounted total otherwise.
        if loyalty['error']:
            request.env.cr.rollback()
            return {'ok': False, 'error': loyalty['error']}
        if reward_id and quote['reward_error']:
            request.env.cr.rollback()
            return {'ok': False, 'error': quote['reward_error']}
        # Loyalty points only ever belong to a signed-in customer: a signed-out request
        # asking to spend any is refused outright rather than silently priced without.
        if not partner and (kwargs.get('points_service_ids') or str(loyalty_points or '0') not in ('0', '')):
            request.env.cr.rollback()
            return {'ok': False, 'error': 'Sign in to use your loyalty points.'}
        reward = quote['reward']
        service_points = [e for e in quote['service_points'] if e['applied']]
        # Points the customer asked to use on a service but the live balance no longer
        # covers (e.g. spent on another booking since the Confirm screen was priced) --
        # refused rather than silently charging the undiscounted price.
        short = [e for e in quote['service_points'] if e.get('selected') and not e['applied']
                 and params.get('points_service_ids') is not None]
        if short:
            request.env.cr.rollback()
            return {'ok': False, 'error': 'Not enough loyalty points left for %s (%d pts). '
                                          'Please review your points and confirm again.'
                                          % (short[0]['service'].name, short[0]['points'])}
        if gift_card_code and quote['gift_card_error']:
            request.env.cr.rollback()
            return {'ok': False, 'error': quote['gift_card_error']}
        promo = quote['promo']
        if str(kwargs.get('promo_code') or '').strip() and quote['promo_error']:
            request.env.cr.rollback()
            return {'ok': False, 'error': quote['promo_error']}

        services = selection['services']
        notes = list(selection['notes'])
        loyalty_redeemed_amount = selection['reward_redeemed_amount']
        if reward:
            loyalty_redeemed_amount += quote['reward_amount']
            notes.append('Loyalty reward used on the site: %s (%d points, ₹%d off)'
                         % (reward.description or reward.display_name or '',
                            int(reward.required_points), int(quote['reward_amount'])))
        for entry in service_points:
            loyalty_redeemed_amount += entry['amount']
            notes.append('Service loyalty points used: %s (%d points, ₹%d off)'
                         % (entry['service'].name, entry['points'], int(entry['amount'])))
        if loyalty['points']:
            loyalty_redeemed_amount += loyalty['amount']
            notes.append('Loyalty points redeemed on the site: %d points (₹%d off)'
                         % (loyalty['points'], int(loyalty['amount'])))
        if promo['reward']:
            notes.append('Discount code applied on the site: %s (%s, ₹%d off)'
                         % (promo['code'], promo['reward'].program_id.name or promo['reward'].description,
                            int(quote['payload']['promo']['amount'])))
        if gift_card:
            notes.append('Gift card applied on the site: %s (₹%d of ₹%d balance)'
                         % (gift_card.code,
                            int(quote['payload']['gift_card']['applied']),
                            int(gift_card.points)))
        notes.append('Requested date: %s' % booking_date.strftime('%A, %d %B %Y'))
        if not str(slot_label or '').strip():
            notes.append('Requested time: not chosen -- please confirm a time with the customer.')
        if not selection['chairs'] and not chair_numbers:
            notes.append('Chair preference: none -- any free chair.')
        if contact['name']:
            notes.append('Customer contact: %s' % ' · '.join(
                v for v in (contact['name'], contact['phone'], contact['email']) if v))
        notes.append('Services and time still to be confirmed with the customer.')

        try:
            # The website no longer shows or enforces the chair/slot conflict
            # check (see enrich_redesign.py's date/time patches) -- a website
            # booking must therefore never be rejected by that same check
            # server-side either, so it is skipped here. bsi_preferred_date
            # (and every other selection) is still recorded on the lead
            # exactly as chosen, so staff reviewing CRM see the real request
            # and can resolve any actual double-booking by hand.
            lead = request.env['crm.lead'].sudo().with_context(
                bsi_skip_slot_capacity_check=True).create({
                'name': ' - '.join(v for v in ('Salon Booking', store_name or 'Website', contact['name']) if v),
                'type': 'opportunity',
                'bsi_lead_source': 'website_booking',
                # crm.lead.user_id defaults to self.env.user, which .sudo() does not change --
                # left unset, a signed-in customer's own login becomes the lead's Salesperson,
                # which then hides it from every real salesperson (crm's own record rule only
                # shows a salesperson their OWN leads or ones with no salesperson at all) and
                # made every site booking look like it silently never reached CRM the moment
                # anyone other than a full-access user (e.g. an Administrator) was signed in
                # while booking. False here leaves it a real unassigned lead instead.
                'user_id': False,
                'partner_id': partner.id if partner else False,
                # The signed-in customer's own account details (plus a mobile they
                # added on the Confirm step when the account had none) -- see
                # enrich_confirm.resolve_contact above.
                'contact_name': contact['name'] or False,
                'email_from': contact['email'] or False,
                'phone': contact['phone'] or False,
                'bsi_city': location.bsi_city if location else False,
                'bsi_location_id': location.id if location else False,
                'bsi_chair_ids': [(6, 0, selection['chairs'].ids)] if selection['chairs'] else False,
                'bsi_artist_id': selection['artist'].id if selection['artist'] else False,
                'bsi_preferred_date': booking_date,
                'bsi_slot_id': selection['slot'].id if selection['slot'] else False,
                # A fixed slot, else the exact custom time picked on the site.
                'bsi_use_slot': bool(selection['slot']) or selection['custom_time'] is None,
                'bsi_preferred_time': selection['custom_time'] or 0.0,
                'bsi_is_member': bool(is_member),
                'bsi_service_ids': [(6, 0, services.ids)] if services else False,
                'bsi_package_id': selection['package'].id if selection['package'] else False,
                'bsi_offer_id': selection['offer'].id if selection['offer'] else False,
                'bsi_addon_ids': [(6, 0, selection['addons'].ids)] if selection['addons'] else False,
                'bsi_loyalty_redeemed_amount': loyalty_redeemed_amount,
                # The mixin prices the code itself (bsi_promo_discount_amount), the same
                # figure the Confirm screen showed.
                'bsi_promo_code': promo['code'] if promo['reward'] else False,
                'bsi_promo_reward_id': promo['reward'].id if promo['reward'] else False,
                'bsi_promo_coupon_id': promo['coupon'].id if promo['coupon'] else False,
                'bsi_use_gift_card': bool(gift_card),
                'bsi_gift_card_id': gift_card.id if gift_card else False,
                # The whole balance is offered and the mixin clamps it to whatever is
                # still owed (see bsi_gift_card_applied_amount) -- the same figure the
                # Confirm screen showed, and the exact amount spent off the real card
                # once this lead is Won.
                'bsi_gift_card_redeem_amount': gift_card.points if gift_card else 0.0,
                'bsi_notes': '\n'.join(notes),
            })
            # Points are spent in the same transaction as the lead, so a booking that is
            # rejected never leaves the customer's points spent. Each spend re-checks the
            # live balance.
            Loyalty = request.env['loyalty.card'].sudo()
            if reward:
                reward._bsi_redeem_for(partner, lead=lead)
            for entry in service_points:
                Loyalty._bsi_spend_points(
                    partner, entry['points'], 'Service points: %s' % entry['service'].name,
                    lead=lead, service=entry['service'])
            if loyalty['points']:
                Loyalty._bsi_spend_points(
                    partner, loyalty['points'],
                    'points on a website booking%s'
                    % (' at %s' % store_name if store_name else ''), lead=lead)
            # A single-use coupon is spent with the booking, in the same transaction (a
            # rejected booking gives it back), so it cannot be used on a second booking.
            if promo['coupon'] and promo['reward']:
                coupon = promo['coupon'].sudo()
                if coupon.points < promo['reward'].required_points:
                    raise UserError('The coupon "%s" has already been used.' % coupon.code)
                coupon.points -= promo['reward'].required_points
        except (UserError, ValidationError) as exc:
            # The shared slot-capacity constraint (a chair or artist already booked for
            # this exact slot -- see bsi_salon_booking_mixin._bsi_check_slot_capacity_common)
            # raises after the row is already written inside this request's transaction.
            # Because it is caught here rather than reaching the dispatcher, roll back
            # explicitly so a rejected request is never committed -- which also unspends
            # the loyalty points above. Its message is deliberately customer-facing
            # already (e.g. "Colour Chair 1 is already booked for the ... slot"), unlike
            # a bare Exception below, so it is safe to hand straight back to the site
            # instead of just logging it -- see enrich_patches.CONFIRM_DST, which now
            # actually checks res.ok before showing the confirmed ticket, rather than
            # always showing it regardless.
            request.env.cr.rollback()
            _logger.info('Enrich site: booking rejected (%s)', exc)
            return {'ok': False, 'error': str(exc)}
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: booking request could not be recorded')
            return {'ok': False}

        # The real balance after the spend above, so the page can show it straight away.
        points_spent = quote['payload']['loyalty']['used'] if partner else 0
        return {'ok': True, 'lead_id': lead.id, 'amount_total': quote['payload']['amount_total'],
                'loyalty_points_spent': points_spent,
                'loyalty_balance': partner.bsi_loyalty_points if partner else 0}

    @http.route('/salon/api/contact', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_contact(self, name=None, email=None, phone=None, notes=None,
                              location_id=None, city=None, **kwargs):
        """Record a contact enquiry from the site as a CRM lead.

        An enquiry with neither an email nor a phone number is refused: there would
        be no way to answer it. PHASE 8 DEV -- the form now asks for the visitor's
        city and branch, so the lead is created already assigned to that branch:
        bsi_location_id drives the lead's company (crm.lead._bsi_apply_location_company),
        which is what lets each branch see only its own enquiries in CRM, and the
        pipeline can be grouped by branch. The branch must be a real, active one --
        the id comes from the browser, so it is re-checked here rather than trusted.
        """
        email = (email or '').strip()
        phone = (phone or '').strip()
        name = (name or '').strip()
        if not email and not phone:
            return {'ok': False, 'error': 'Please add an email or a phone number so we can reply.'}

        location = request.env['bsi.salon.location'].sudo().browse(
            int(location_id) if str(location_id or '').isdigit() else 0).exists()
        if location and not location.active:
            location = location.browse()
        if location_id and not location:
            return {'ok': False, 'error': 'Please choose one of our branches from the list.'}

        try:
            lead = request.env['crm.lead'].sudo().create({
                'name': 'Salon Contact - %s%s' % (
                    name or email or phone, (' (%s)' % location.name) if location else ''),
                'type': 'opportunity',
                # See bsi_salon_api_booking's same 'user_id': False for why -- otherwise a
                # signed-in visitor's own login becomes the lead's Salesperson.
                'user_id': False,
                'contact_name': name or False,
                'email_from': email or False,
                'phone': phone or False,
                'bsi_lead_source': 'contact_form',
                'bsi_location_id': location.id if location else False,
                'bsi_city': location.bsi_city if location else False,
                # A contact enquiry is not a booking request -- no date is being asked
                # for, so the booking-date default (today) is left off.
                'bsi_preferred_date': False,
                'bsi_notes': (notes or '').strip() or False,
            })
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: contact enquiry could not be recorded')
            return {'ok': False}

        return {'ok': True, 'lead_id': lead.id,
                'branch': location.name if location else '', 'city': location.bsi_city if location else ''}

    @http.route('/salon/api/membership_product', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_membership_product(self, membership_id=None, billing_period='monthly', **kwargs):
        """Resolve a membership tier to the product that sells it.

        The tier's product is created on first use by the salon module's own
        helper, so pricing stays owned by bsi_salon_backend. From here the design
        hands over to the standard Odoo cart and checkout.
        """
        membership = request.env['bsi.salon.membership'].sudo().browse(
            int(membership_id) if str(membership_id or '').isdigit() else 0).exists()
        if not membership:
            return {'error': True}

        period = billing_period if billing_period in ('monthly', 'yearly') else 'monthly'
        try:
            product = membership._bsi_get_or_create_product(period)
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: membership product could not be resolved')
            return {'error': True}

        return {
            'product_id': product.id,
            'product_template_id': product.product_tmpl_id.id,
        }

    @http.route('/salon/api/membership_status', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_membership_status(self, **kwargs):
        """Whether the signed-in visitor has an active membership right now.

        The served page is cached and shared by every visitor (see
        _PAGE_CACHE above), so this can never be baked into it -- the site
        has to ask at runtime instead, one request per visitor, and gets
        nothing back for the public user.

        PHASE 4 DEV: was 'bsi_state' == 'active' alone -- that field only
        flips to 'expired' once a day, on _cron_bsi_expire_subscriptions, so a
        subscription whose bsi_end_date has already passed today still read
        as active here for up to ~24h. Now checks bsi_end_date >= today too,
        the same combination bsi_salon_booking_mixin._bsi_find_active_
        subscriptions treats as the one canonical "genuinely active" test --
        this endpoint has to stay in lockstep with it, since the website now
        auto-applies the discount straight off what this call reports (see
        enrich_patches.MOUNT_DST/CONFIRM_DST) rather than gating on a
        customer checkbox any more. Also now returns the plan's own start/
        expiry dates and perks for the new "Active Membership Plan" section
        (see enrich_patches.MEMBERSHIP_BANNER_*), and picks the
        highest-discount subscription if more than one is somehow active at
        once, same tie-break _bsi_compute_bsi_amounts_common uses.
        """
        user = request.env.user
        if user._is_public():
            return {'active': False}

        today = fields.Date.context_today(request)
        subscriptions = request.env['bsi.salon.membership.subscription'].sudo().search([
            ('bsi_partner_id', '=', user.partner_id.id),
            ('bsi_state', '=', 'active'),
            ('bsi_end_date', '>=', today),
        ])
        if not subscriptions:
            return {'active': False}

        subscription = max(subscriptions, key=lambda s: s.bsi_membership_id.bsi_discount_percent)
        membership = subscription.bsi_membership_id
        return {
            'active': True,
            'tier_name': membership.name,
            'discount_percent': membership.bsi_discount_percent or 0,
            'start_date': subscription.bsi_start_date.isoformat() if subscription.bsi_start_date else '',
            'expiry_date': subscription.bsi_end_date.isoformat() if subscription.bsi_end_date else '',
            'perks': [p.strip() for p in (membership.bsi_perks or '').splitlines() if p.strip()],
        }

    @http.route('/salon/api/gift_card_product', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_gift_card_product(self, amount=None, **kwargs):
        """Resolve a chosen gift card amount to the product that sells it.

        Same pattern as membership_product: the denomination's product is
        created on first use, then the design hands over to the standard cart
        and checkout. Matched on amount rather than an id because the design's
        own giftAmount state is just the number the customer picked.
        """
        # Resolve the gift card trigger product from the loyalty.program's rule product list.
        # In Odoo v19, loyalty.program has no gift_card_product_id; the product the
        # customer buys is stored in trigger_product_ids (related to rule_ids.product_ids).
        if not amount:
            return {'error': True}
        program = request.env['loyalty.program'].sudo().search(
            [('name', '=', 'Salon Gift Card'), ('program_type', '=', 'gift_card')], limit=1)
        product = program.trigger_product_ids[:1] if program else request.env['product.product']
        if not program or not product:
            return {'error': True}
        return {
            'product_id': product.id,
            'product_template_id': product.product_tmpl_id.id,
        }

    @http.route('/salon/api/gift_card_status', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_gift_card_status(self, **kwargs):
        """The signed-in visitor's own currently usable gift card, if any.

        Same reasoning as membership_status/loyalty_status: the served page is
        cached and shared by every visitor, so this can only be answered at
        request time. Matched by purchaser email, same lookup
        bsi_salon_booking_mixin._bsi_find_active_gift_card uses once a real
        booking exists -- this just answers the same question earlier, so the
        Gift Cards panel can show it before any booking is even started.
        """
        user = request.env.user
        if user._is_public() or not user.partner_id.email:
            return {'active': False, 'cards': []}

        # Any gift card program (as _bsi_find_active_gift_card), not only "Salon Gift Card".
        cards = request.env['loyalty.card'].sudo().search([
            ('partner_id.email', '=', user.partner_id.email),
            ('program_id.program_type', '=', 'gift_card'),
            ('program_id.active', '=', True),
        ], order='create_date desc')

        today = fields.Date.context_today(request)
        cards_list = [{
            'code': c.code,
            'amount': round(c.points, 2),
            'balance': round(c.points, 2),
            'state': 'active' if c.points > 0 and not (c.expiration_date and c.expiration_date < today) else 'used',
            'active': c.points > 0 and not (c.expiration_date and c.expiration_date < today),
        } for c in cards]

        primary = next((c for c in cards_list if c['active']), None)
        return {
            'active': bool(primary),
            'code': primary['code'] if primary else '',
            'balance': primary['balance'] if primary else 0,
            'cards': cards_list,
        }

    @http.route('/salon/api/loyalty_status', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_loyalty_status(self, **kwargs):
        """The signed-in visitor's own loyalty point balance right now.

        Same reasoning as membership_status: the served page is cached and
        shared by every visitor, so "how many points do I have" (and
        therefore which of a service's "Redeem for points" buttons are
        actually usable) can only be answered at request time, per visitor.
        """
        user = request.env.user
        rules = request.env['loyalty.card'].sudo()._bsi_get_redemption_rules()
        # PHASE 6 DEV -- the configured redemption rules ride along, so the booking
        # Confirm screen can state them ("100 points minimum", "up to 50% of this
        # booking") without a second call and without knowing them itself. What a
        # given redemption is actually worth still only ever comes from
        # /salon/api/booking_quote -- these are for display.
        payload = {
            'point_value': rules['point_value'],
            'min_points': rules['min_points'],
            'max_percent': rules['max_percent'],
        }
        if user._is_public():
            return dict(payload, points=0)
        return dict(payload, points=user.partner_id.bsi_loyalty_points)

    @http.route('/salon/api/user_status', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_user_status(self, **kwargs):
        """Who is looking at the page right now, for the navbar's account controls.

        The served page is one cached document shared by every visitor (see
        _PAGE_CACHE), so "show Dashboard", "show Log out" and the visitor's own name
        can never be baked into it -- the navbar asks at runtime instead, the same
        reason membership_status/loyalty_status are runtime calls.

        is_admin is base.group_system alone, deliberately not base.group_user: the
        salon dashboard at /salon/dashboard is a management console (revenue, staff
        utilisation, every branch's pipeline), so an ordinary employee signing in on
        the website gets the same account controls a customer does and no Dashboard
        button at all.
        """
        user = request.env.user
        if user._is_public():
            return {'logged_in': False, 'is_admin': False, 'name': ''}
        return {
            'logged_in': True,
            'is_admin': user.has_group('base.group_system'),
            'name': user.partner_id.name or user.name or '',
        }

    @http.route('/salon/api/loyalty_redeem', type='jsonrpc', auth='user', website=True)
    def bsi_salon_api_loyalty_redeem(self, reward_id=None, service_id=None, **kwargs):
        """Spend loyalty points for the signed-in customer, on either a curated reward
        or directly on a service's own bsi_loyalty_points -- exactly one of reward_id/
        service_id is expected.

        auth='user' rather than 'public': spending points only ever makes
        sense for a real, identified customer, and both _bsi_redeem_for methods need a
        real partner to check the balance against and write the ledger entry
        to -- there is no "guest redemption" to support.

        Retired: it spent the points on the spot, before (and without) any booking, and
        the page no longer calls it. Points are now applied on the booking itself and
        spent once, when that booking is confirmed (see _bsi_booking_quote and
        bsi_salon_api_booking), so nothing is spent here any more.
        """
        return {'ok': False, 'error': 'Loyalty points are applied on the booking\'s Confirm '
                                      'step and used when you confirm it.'}
        # pylint: disable=unreachable
        partner = request.env.user.partner_id
        reward = request.env['loyalty.reward'].sudo().browse(
            int(reward_id) if str(reward_id or '').isdigit() else 0).exists()
        service = request.env['bsi.salon.service'].sudo().browse(
            int(service_id) if str(service_id or '').isdigit() else 0).exists()

        if reward:
            try:
                reward._bsi_redeem_for(partner)
            except UserError as exc:
                return {'ok': False, 'error': str(exc)}
            except Exception:
                request.env.cr.rollback()
                _logger.exception('Enrich site: loyalty reward could not be redeemed')
                return {'ok': False}
            # points is the balance AFTER this redemption -- without it, the site has no way
            # to update the wallet display or any other service's "Redeem N pts" button
            # (both keyed off the same client-side loyaltyPoints state, set once on page
            # load) without a full page reload, so a customer redeeming two services in one
            # visit would see the FIRST one's now-stale, pre-redemption balance the whole
            # time, and could see a second service as still affordable/clickable when the
            # real balance underneath it no longer covers it (the actual spend is still
            # safe either way -- _bsi_redeem_for re-checks the real balance -- just the
            # button's own enabled/disabled state would be wrong).
            return {
                'ok': True,
                'service_id': None,
                'service_name': None,
                # This reward's own points cost (1 point = ₹1) -- the discount earned, not
                # the entitled service's price (see bsi_salon_api_booking's own reasoning).
                'redeemed_amount': int(reward.required_points),
                'points': partner.bsi_loyalty_points,
            }

        if service:
            try:
                service._bsi_redeem_loyalty_for(partner)
            except UserError as exc:
                return {'ok': False, 'error': str(exc)}
            except Exception:
                request.env.cr.rollback()
                _logger.exception('Enrich site: loyalty points could not be redeemed for a service')
                return {'ok': False}
            # See the reward branch above for why points (the post-redemption balance) is
            # returned here too.
            return {
                'ok': True,
                'service_id': service.id,
                'service_name': service.name,
                # This service's own points value (1 point = ₹1) -- the discount earned,
                # not its price (see bsi_salon_api_booking's own reasoning).
                'redeemed_amount': float(service.bsi_loyalty_points),
                'points': partner.bsi_loyalty_points,
            }

        return {'ok': False}

    @http.route('/salon/api/branch_chairs', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_branch_chairs(self, location_id=None, **kwargs):
        """The real chairs configured for one branch, for the booking wizard's chair step.

        The served page is cached and shared by every visitor (see
        _PAGE_CACHE above) and has no branch selected yet when it is built, so
        which chairs to show can only be known once the customer actually
        picks a branch -- this is asked for at that point instead, the same
        reason membership_status is a runtime call rather than baked in.
        """
        location = request.env['bsi.salon.location'].sudo().browse(
            int(location_id) if str(location_id or '').isdigit() else 0).exists()
        if not location:
            return []

        chairs = request.env['bsi.salon.chair'].sudo().search(
            [('bsi_location_id', '=', location.id)], order='sequence, id')
        return [{
            'id': chair.id,
            'style_key': chair.bsi_style_id.bsi_key or None,
        } for chair in chairs]

    @http.route('/salon/api/customer_city', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_customer_city(self, **kwargs):
        """The signed-in customer's own city, resolved to a CITIES entry the site knows.

        Read off their contact address (res.partner.city) -- there is nothing
        more specific to go on (no "home branch" concept exists on a
        customer). Guests and a city we have no branch in both just get None,
        which the booking wizard's own city-picker step already handles.
        """
        user = request.env.user
        if user._is_public():
            return {'city_id': None}

        partner_city = (user.partner_id.city or '').strip()
        if not partner_city:
            return {'city_id': None}

        Data = request.env['bsi.enrich.data'].sudo()
        slug = Data._bsi_city_slug(partner_city)
        known_ids = {city['id'] for city in Data._bsi_cities()}
        return {'city_id': slug if slug in known_ids else None}
