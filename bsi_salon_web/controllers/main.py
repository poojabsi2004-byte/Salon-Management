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
import logging
import re

from odoo import fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.tools import file_open

from . import enrich_patches

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
    consts = (
        ('BSI_LOOK_FINISHES', finishes),
        ('BSI_LOOK_LENGTHS', lengths),
        ('BSI_LOOK_BASE_PRICE', base_price),
        ('BSI_CONSULT_RULES', rules),
        ('BSI_ADDONS', addons),
        ('BSI_PACKAGES', packages),
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

        # The block holds a complete JSON string literal, quotes included, so the
        # replacement keeps the quotes json.dumps puts back.
        return raw[:match.start(2)] + _js_safe(json.dumps(page)) + raw[match.end(2):]

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
                                        chair_ids=None, artist_id=None, **kwargs):
        """Which fixed slots are still open at a branch on a date.

        Returns {slot_id: True/False}. A pending CRM lead holds a slot exactly as
        a confirmed appointment does -- that rule lives in the mixin's conflict
        domains and is not re-stated here.
        """
        location = request.env['bsi.salon.location'].sudo().browse(
            int(location_id) if str(location_id or '').isdigit() else 0).exists()
        if not location or not preferred_date:
            return {}

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
        return result

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

    @http.route('/salon/api/booking', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_booking(self, location_id=None, slot_label=None, chair_numbers=None,
                              is_member=False, city_name=None, store_name=None,
                              reward_service_id=None, artist_id=None, look_length=None,
                              look_shade_index=None, look_finish=None, addon_keys=None,
                              selected_service_id=None, selected_service_ids=None,
                              package_id=None, **kwargs):
        """Record a booking request from the site as a CRM lead.

        A lead rather than an appointment, which is the route the salon's own
        booking form took as well: staff review it and the appointment is built
        when the lead is marked Won.

        The design's wizard still collects no date and no contact details --
        those stay Phase 3, noted for staff to ask. chair_numbers are real
        bsi.salon.chair ids now the chair step is branch-specific (see
        enrich_patches.CHAIRS_STORE_DST); each is checked against the chosen
        branch before being trusted onto bsi_chair_ids, so a stale cached page
        still sending the design's old 1-10 studio positions just degrades to
        the note-only behaviour below instead of wrongly claiming a chair.

        reward_service_id carries a loyalty reward's service through from
        /salon/api/loyalty_redeem (see enrich_patches.REDEEM_DST) -- points are
        already spent by the time this fires, so the service is set for real on
        bsi_service_ids rather than only noted, same as any other real field.

        artist_id carries the stylist from "Book with this stylist" (see
        enrich_patches.CONFIRM_DST reading state.bookingStylist) -- unset for
        every other way into the wizard, same as reward_service_id.

        look_length/look_shade_index/look_finish carry the Design-Your-Look
        configurator's choice through from "Book this look" (see
        enrich_patches.LOOK_METHOD_DST) -- length and finish are the same
        bsi_key strings the configurator itself uses, shade is the array
        index into LOOK_SHADES the configurator's own state stores, since
        that data has no id of its own on the served page.

        addon_keys carries the chair-side ritual builder's picks (see
        enrich_patches.CONFIRM_DST reading state.ritual) -- each is one of
        bsi.salon.addon's own bsi_key values, the same fixed massage/towel/
        aroma/drink/music slots the ritual builder's markup is keyed on, so
        their price now reaches bsi_addon_ids instead of being shown on the
        site and then thrown away.

        selected_service_id carries a plain "Book" click straight off the
        Services page (see enrich_patches.SERVICE_POINTS_METHOD_DST's
        goBookingWithService) -- priced normally, unlike reward_service_id,
        which is only ever set once its points are already spent.

        selected_service_ids carries the booking wizard's own Service step
        (see enrich_patches.STEP_SERVICE_METHOD_DST's bookingToggleService/
        bookingServicesNext) -- a customer can pick more than one service
        there, unlike the single-service selected_service_id above, so this
        is a list. Both are unioned onto bsi_service_ids together with
        reward_service and any Design-Your-Look service below, exactly the
        multi-service shape bsi_salon_booking_mixin already prices.

        package_id carries a bundle picked on the Service step or the
        Services page (see enrich_patches.STEP_SERVICE_METHOD_DST's
        bookingApplyPackage). Packages are exclusive with individual
        services on bsi.salon.booking.mixin (_bsi_check_package_exclusive_common
        requires bsi_service_ids to exactly equal the package's own
        bsi_service_ids whenever bsi_package_id is set) -- rather than trust
        whatever selected_service_id(s) happen to still be in the request
        alongside a package (stale wizard state, or a crafted request), this
        always sets bsi_service_ids from the package's own services and
        ignores selected_service_id/selected_service_ids/reward_service_id
        entirely whenever a package is present, the same way the wizard's
        own bookingApplyPackage overwrites bookingServiceIds client-side.

        A signed-in customer's own contact details are read off request.env.user
        rather than left for staff to ask -- a guest checkout still has nothing
        to read (auth='public' means user._is_public() then), same guard
        membership_status/customer_city already use for the same reason.
        """
        user = request.env.user
        partner = user.partner_id if not user._is_public() else request.env['res.partner']
        location = request.env['bsi.salon.location'].sudo().browse(
            int(location_id) if str(location_id or '').isdigit() else 0).exists()
        reward_service = request.env['bsi.salon.service'].sudo().browse(
            int(reward_service_id) if str(reward_service_id or '').isdigit() else 0).exists()
        selected_service = request.env['bsi.salon.service'].sudo().browse(
            int(selected_service_id) if str(selected_service_id or '').isdigit() else 0).exists()
        selected_services = request.env['bsi.salon.service'].sudo().browse(
            [int(i) for i in (selected_service_ids or []) if str(i).isdigit()]).exists()
        package = request.env['bsi.salon.package'].sudo().browse(
            int(package_id) if str(package_id or '').isdigit() else 0).exists()
        artist = request.env['bsi.salon.team.member'].sudo().browse(
            int(artist_id) if str(artist_id or '').isdigit() else 0).exists()

        slot = request.env['bsi.salon.time.slot']
        if slot_label:
            _labels, lookup = request.env['bsi.enrich.data'].sudo()._bsi_time_slots()
            slot_id = lookup.get(str(slot_label).strip())
            if slot_id:
                slot = slot.sudo().browse(slot_id)

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
        loyalty_redeemed_amount = 0.0
        if reward_service:
            # The points value (1 point = ₹1), NOT this service's own price -- a customer
            # who redeemed points still pays for the service at its normal price, just
            # discounted by however many points it cost them (see
            # bsi.salon.service._bsi_get_points_redeemed_value, which also covers a curated
            # reward's own points cost, since reward_service_id carries either kind of
            # redemption through identically by the time it reaches here).
            loyalty_redeemed_amount = reward_service._bsi_get_points_redeemed_value()
            notes.append('Loyalty points redeemed against: %s (₹%d off)'
                         % (reward_service.name, int(loyalty_redeemed_amount)))

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
        if package:
            services = package.bsi_service_ids
            notes.append('Package selected on the site: %s' % package.name)
        else:
            services = reward_service
            if selected_service:
                services |= selected_service
                notes.append('Service selected on the site: %s' % selected_service.name)
            if selected_services:
                services |= selected_services
                notes.append('Services selected on the site: %s'
                             % ', '.join(selected_services.mapped('name')))
        if not package and (look_length or look_finish or look_shade_index is not None):
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
            base_price = next((l.bsi_base_price for l in lengths if l.bsi_base_price), 2999)
            total = (base_price + (length_rec.bsi_surcharge or 0) + (shade_rec.bsi_surcharge or 0)
                     + (finish_rec.bsi_surcharge or 0))
            parts = [rec.name for rec in (length_rec, shade_rec, finish_rec) if rec]
            if parts:
                look_summary = ' · '.join(parts)
                # A real bsi.salon.service, one per booking, rather than a pair of plain
                # fields on the lead -- so this booking's Services/Services Amount/Total
                # Amount populate exactly the way a normal service-based booking's do, and
                # the length/shade/finish behind the number are one click away on the
                # service's own form. bsi_is_custom_look keeps it out of the website's own
                # Services list and the main Services catalog menu (see their own domains).
                look_service = request.env['bsi.salon.service'].sudo().create({
                    'name': look_summary,
                    'bsi_category': 'hair',
                    'bsi_is_custom_look': True,
                    'bsi_look_length_id': length_rec.id if length_rec else False,
                    'bsi_look_shade_id': shade_rec.id if shade_rec else False,
                    'bsi_look_finish_id': finish_rec.id if finish_rec else False,
                    'bsi_price': '₹%d' % int(total),
                    'bsi_price_amount': total,
                })
                services |= look_service
                notes.append('Look configured on the site: %s — estimated ₹%d'
                              % (look_summary, int(total)))

        notes.append('Date, services and contact details still to be confirmed with the customer.')

        try:
            lead = request.env['crm.lead'].sudo().create({
                'name': 'Salon Booking - %s' % (store_name or 'Website'),
                'type': 'opportunity',
                # crm.lead.user_id defaults to self.env.user, which .sudo() does not change --
                # left unset, a signed-in customer's own login becomes the lead's Salesperson,
                # which then hides it from every real salesperson (crm's own record rule only
                # shows a salesperson their OWN leads or ones with no salesperson at all) and
                # made every site booking look like it silently never reached CRM the moment
                # anyone other than a full-access user (e.g. an Administrator) was signed in
                # while booking. False here leaves it a real unassigned lead instead.
                'user_id': False,
                'partner_id': partner.id if partner else False,
                'contact_name': partner.name if partner else False,
                'email_from': partner.email if partner else False,
                'phone': partner.phone if partner else False,
                'bsi_city': location.bsi_city if location else False,
                'bsi_location_id': location.id if location else False,
                'bsi_chair_ids': [(6, 0, chairs.ids)] if chairs else False,
                'bsi_artist_id': artist.id if artist else False,
                'bsi_slot_id': slot.id if slot else False,
                'bsi_use_slot': bool(slot),
                'bsi_is_member': bool(is_member),
                'bsi_service_ids': [(6, 0, services.ids)] if services else False,
                'bsi_package_id': package.id if package else False,
                'bsi_addon_ids': [(6, 0, addons.ids)] if addons else False,
                'bsi_loyalty_redeemed_amount': loyalty_redeemed_amount,
                'bsi_notes': '\n'.join(notes),
            })
        except ValidationError as exc:
            # The shared slot-capacity constraint (a chair or artist already booked for
            # this exact slot -- see bsi_salon_booking_mixin._bsi_check_slot_capacity_common)
            # raises after the row is already written inside this request's transaction.
            # Because it is caught here rather than reaching the dispatcher, roll back
            # explicitly so a rejected request is never committed. Its message is
            # deliberately customer-facing already (e.g. "Colour Chair 1 is already
            # booked for the ... slot"), unlike a bare Exception below, so it is safe to
            # hand straight back to the site instead of just logging it -- see
            # enrich_patches.CONFIRM_DST, which now actually checks res.ok before
            # showing the confirmed ticket, rather than always showing it regardless.
            request.env.cr.rollback()
            _logger.info('Enrich site: booking rejected (%s)', exc)
            return {'ok': False, 'error': str(exc)}
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: booking request could not be recorded')
            return {'ok': False}

        return {'ok': True, 'lead_id': lead.id}

    @http.route('/salon/api/contact', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_contact(self, name=None, email=None, phone=None, notes=None, **kwargs):
        """Record a contact enquiry from the site as a CRM lead.

        The design shows its thank-you the moment the form is submitted and waits
        on nothing, so this only has to persist what was typed. An enquiry with
        neither an email nor a phone number is dropped: there would be no way to
        answer it.
        """
        email = (email or '').strip()
        phone = (phone or '').strip()
        name = (name or '').strip()
        if not email and not phone:
            return {'ok': False}

        try:
            lead = request.env['crm.lead'].sudo().create({
                'name': 'Salon Contact - %s' % (name or email or phone),
                'type': 'opportunity',
                # See bsi_salon_api_booking's same 'user_id': False for why -- otherwise a
                # signed-in visitor's own login becomes the lead's Salesperson.
                'user_id': False,
                'contact_name': name or False,
                'email_from': email or False,
                'phone': phone or False,
                'bsi_notes': (notes or '').strip() or False,
            })
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: contact enquiry could not be recorded')
            return {'ok': False}

        return {'ok': True, 'lead_id': lead.id}

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
        denomination = request.env['bsi.salon.gift.denomination'].sudo().search(
            [('bsi_amount', '=', float(amount))], limit=1) if amount else None
        if not denomination:
            return {'error': True}

        try:
            product = denomination._bsi_get_or_create_product()
        except Exception:
            request.env.cr.rollback()
            _logger.exception('Enrich site: gift card product could not be resolved')
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
            return {'active': False}

        card = request.env['bsi.salon.gift.card'].sudo().search([
            ('bsi_purchaser_id.email', '=', user.partner_id.email),
            ('bsi_state', '=', 'active'), ('bsi_balance', '>', 0),
        ], order='create_date desc', limit=1)
        if not card:
            return {'active': False}

        return {'active': True, 'code': card.bsi_code, 'balance': card.bsi_balance}

    @http.route('/salon/api/loyalty_status', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_loyalty_status(self, **kwargs):
        """The signed-in visitor's own loyalty point balance right now.

        Same reasoning as membership_status: the served page is cached and
        shared by every visitor, so "how many points do I have" (and
        therefore which of a service's "Redeem for points" buttons are
        actually usable) can only be answered at request time, per visitor.
        """
        user = request.env.user
        if user._is_public():
            return {'points': 0}
        return {'points': user.partner_id.bsi_loyalty_points}

    @http.route('/salon/api/loyalty_redeem', type='jsonrpc', auth='user', website=True)
    def bsi_salon_api_loyalty_redeem(self, reward_id=None, service_id=None, **kwargs):
        """Spend loyalty points for the signed-in customer, on either a curated reward
        or directly on a service's own bsi_loyalty_points -- exactly one of reward_id/
        service_id is expected.

        auth='user' rather than 'public': spending points only ever makes
        sense for a real, identified customer, and both _bsi_redeem_for methods need a
        real partner to check the balance against and write the ledger entry
        to -- there is no "guest redemption" to support.
        """
        partner = request.env.user.partner_id
        reward = request.env['bsi.salon.loyalty.reward'].sudo().browse(
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
                'service_id': reward.bsi_service_id.id or None,
                'service_name': reward.bsi_service_id.name or None,
                # This reward's own points cost (1 point = ₹1) -- the discount earned, not
                # the entitled service's price (see bsi_salon_api_booking's own reasoning).
                'redeemed_amount': reward.bsi_points_cost,
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
