# -*- coding: utf-8 -*-
"""Home page Recommended section from backend data.

The design's "Recommended for you" cards (`recommended: [...]`, three hardcoded
services with their own photos, no id, no click handler at all) become backend
data in this order -- see models/bsi_enrich_recommended.py for where each tier
comes from:

  1. A signed-in customer's own booking history: other catalogue services in the
     same category as something they've booked before, resolved at RUNTIME by
     /salon/api/recommended below (the page itself is cached for every visitor,
     see controllers/main.py's _PAGE_CACHE, so nothing customer-specific can be
     baked into the page -- same reason live_pulse/user_status/booking_contact
     are runtime calls instead of baked consts, see enrich_hero.py/enrich_confirm.py).
  2. Admin-curated services (bsi_is_recommended), baked into the page at BUILD time.
  3. The catalogue's most-booked services, also baked in.
  4. The design's own three cards (with their photos), left completely untouched
     when the catalogue has neither of the above -- the page never looks empty.

Tiers 2/3 replace the `recommended: [...]` array literal in place (same
balanced-bracket technique as main.py's own _replace_property, duplicated here in
_value_span so this module doesn't import from main.py's owned render loop); tier
1 then wraps that same property with a runtime override the client fills in after
sign-in, exactly like live_pulse's `pulseFacts: (s.bsiLivePulse || BSI_HERO.pulse)`.

Applied by controllers/enrich_extensions.py after every other patch module, so
anchors here must match the fully patched template (check the served page).
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def _js_safe(dumped):
    return dumped.replace('</', r'<\/')


def _value_span(source, anchor):
    """Return (open_at, close_at) delimiting the JS literal (array/object/string)
    that starts right after `anchor`, or None. source[open_at:close_at+1] is the
    literal including its own delimiters. Balanced-bracket/quote scan, same idea
    as main.py's _replace_value_at, kept local here so this module never has to
    import from the render loop main.py owns."""
    start = source.find(anchor)
    if start == -1:
        return None
    pos = start + len(anchor)
    if pos >= len(source):
        return None
    opening = source[pos]
    if opening in '[{':
        closing = {'[': ']', '{': '}'}[opening]
        depth, index, quote = 0, pos, None
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
                    return pos, index
            index += 1
        return None
    if opening in '"\'`':
        quote = opening
        index = pos + 1
        while index < len(source):
            char = source[index]
            if char == '\\':
                index += 2
                continue
            if char == quote:
                return pos, index
            index += 1
        return None
    return None


def _wrap_value(page, anchor, label, wrapper):
    """Replace the literal after `anchor` with wrapper(current_literal_text)."""
    span = _value_span(page, anchor)
    if not span:
        _logger.warning('Enrich site: %s not found, left as designed', label)
        return page
    open_at, close_at = span
    body = page[open_at:close_at + 1]
    return page[:open_at] + wrapper(body) + page[close_at + 1:]


def _replace_recommended_data(page, rows):
    """Tier 2/3: swap the baked `recommended: [...]` array for real service rows.
    Left untouched (tier 4, the design's own three cards) when `rows` is empty."""
    if not rows:
        return page
    span = _value_span(page, 'recommended: ')
    if not span:
        _logger.warning('Enrich site: recommended data literal not found, left as designed')
        return page
    open_at, close_at = span
    literal = _js_safe(json.dumps(rows, ensure_ascii=False))
    return page[:open_at] + literal + page[close_at + 1:]


SUBTITLE_SRC = (
    '<span style="color:#b3b3b3;font-size:13px;">'
    'Because you loved Global Hair Colour last visit</span>'
)
SUBTITLE_DST = (
    '<span style="color:#b3b3b3;font-size:13px;">{{ recommendedSubtitle }}</span>'
)

# The design's card has an image, a badge, a name/description/price -- and nothing
# clickable at all. This gives it the same "Book ->" ghost link every other service
# card on the site already has (Services page, redeemed-points card), wired to the
# same goBookingWithService() every one of those already uses, so the service it
# names is exactly what the Service step opens pre-selected with.
BOOK_BUTTON_SRC = (
    '<div style="color:#ffffff;font-size:14px;font-weight:700;">{{ r.price }}</div>\n'
    '              </div>'
)
BOOK_BUTTON_DST = (
    '<div style="color:#ffffff;font-size:14px;font-weight:700;">{{ r.price }}</div>\n'
    '                <button sc-camel-on-click="{{ r.bookOnClick }}" style="background:none;'
    'border:none;padding:0;margin-top:10px;font-size:11px;color:#e8283f;font-weight:700;'
    'cursor:pointer;">Book →</button>\n'
    '              </div>'
)

PATCHES = (
    ('recommended subtitle', SUBTITLE_SRC, SUBTITLE_DST),
    ('recommended book button', BOOK_BUTTON_SRC, BOOK_BUTTON_DST),
)


def apply(page, data):
    rows = data.get('recommended') or []
    subtitle = data.get('recommended_subtitle') or ''

    # Capture the design's own three rows (full photos included) before anything
    # else touches them, and inject them as a standalone const -- an admin-picked
    # service with no photo of its own borrows one of these by index below, the
    # same per-card image fallback Featured Services uses, so a card is never
    # left with a blank image.
    design_span = _value_span(page, 'recommended: ')
    design_body = page[design_span[0]:design_span[1] + 1] if design_span else '[]'
    dc_anchor = '<script type="text/x-dc"'
    tag_start = page.find(dc_anchor)
    tag_close = page.find('>', tag_start) if tag_start != -1 else -1
    if tag_close == -1:
        _logger.warning('Enrich site: %s not found, recommended image fallback not injected', dc_anchor)
    else:
        insert_at = tag_close + 1
        page = (page[:insert_at] + 'const BSI_RECOMMENDED_DESIGN = ' + design_body + ';\n'
                 + page[insert_at:])

    # Insert the recommendedSubtitle context key right before `recommended: ` (fresh
    # find each step below, so this text shifting around doesn't break later anchors).
    anchor = 'recommended: '
    idx = page.find(anchor)
    if idx == -1:
        _logger.warning('Enrich site: recommended context key not found, left as designed')
    else:
        key = 'recommendedSubtitle: ' + _js_safe(json.dumps(subtitle, ensure_ascii=False)) + ',\n      '
        page = page[:idx] + key + page[idx:]

    # Markup: static subtitle text / no-op card -> live bindings.
    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)

    # Tier 2/3 baked data (admin-curated or most-booked), tier 4 (design default) left as-is.
    page = _replace_recommended_data(page, rows)

    # Tier 1 runtime override (signed-in customer's own history, see the API route
    # below) wraps whatever ended up in `recommended`/`recommendedSubtitle` above --
    # maps each row to a bookOnClick closure using the service id/name on it (the
    # same way filteredServices/servicePackages already attach one), and gives any
    # row with no photo of its own one of the design's three, by index.
    page = _wrap_value(
        page, 'recommended: ', 'recommended runtime wrap',
        lambda body: (
            '(s.bsiRecommended || ' + body + ').map((r, i) => ({ ...r, '
            "imgSrc: r.imgSrc || ((BSI_RECOMMENDED_DESIGN[i % BSI_RECOMMENDED_DESIGN.length] || {}).imgSrc || ''), "
            'bookOnClick: () => this.goBookingWithService(r.id, r.name) }))'
        ),
    )
    page = _wrap_value(
        page, 'recommendedSubtitle: ', 'recommended subtitle runtime wrap',
        lambda body: '(s.bsiRecommendedSubtitle || ' + body + ')',
    )

    # Fetch the personalised list once on mount, same pattern as the "LIVE right
    # now" strip (see enrich_hero.py's MOUNT_SRC/MOUNT_DST) -- a public/guest
    # visitor's call below always returns an empty result, so bsiRecommended stays
    # unset and the baked tier 2/3/4 content (already wired above) shows instead.
    mount_anchor = (
        "    this._pulseTimer = setInterval(() => this.setState((s) => "
        "({ pulseIdx: (s.pulseIdx + 1) % 4 })), 3600);\n"
    )
    if mount_anchor in page:
        mount_patch = (
            "    fetch('/salon/api/recommended', { method: 'POST', credentials: 'same-origin', "
            "headers: { 'Content-Type': 'application/json' }, "
            "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
            "      .then((r) => r.json()).then((payload) => {\n"
            "        const result = payload && payload.result;\n"
            "        if (result && result.rows && result.rows.length) {\n"
            "          this.setState({ bsiRecommended: result.rows, bsiRecommendedSubtitle: result.subtitle || '' });\n"
            "        }\n"
            "      }).catch(function () {});\n"
        )
        page = page.replace(mount_anchor, mount_anchor + mount_patch, 1)
    else:
        _logger.warning('Enrich site: recommended mount hook not found, left as designed')

    return page


# ---------------------------------------------------------------------------
# Runtime personalisation
# ---------------------------------------------------------------------------

class BsiSalonRecommendedApi(http.Controller):

    @http.route('/salon/api/recommended', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_recommended(self, **kwargs):
        """A signed-in customer's own "Recommended for you": other active catalogue
        services sharing a category with something on their own past bookings,
        most-booked-by-them first, excluding services they've already had. A guest,
        or a signed-in customer with no booking history yet, gets nothing back here
        -- the baked admin/most-booked/design content already on the page stands.
        """
        user = request.env.user
        if user._is_public() or not user.partner_id:
            return {'rows': [], 'subtitle': ''}

        Booking = request.env['bsi.salon.booking.request'].sudo()
        past = Booking.search(
            [('bsi_partner_id', '=', user.partner_id.id), ('bsi_service_ids', '!=', False)],
            order='bsi_preferred_date desc, id desc', limit=20)
        if not past:
            return {'rows': [], 'subtitle': ''}

        booked_services = past.mapped('bsi_service_ids').filtered(lambda s: not s.bsi_is_custom_look)
        if not booked_services:
            return {'rows': [], 'subtitle': ''}

        last_service = past[0].bsi_service_ids.filtered(lambda s: not s.bsi_is_custom_look)[:1]
        categories = booked_services.mapped('bsi_category')
        booked_ids = booked_services.ids

        Service = request.env['bsi.salon.service'].sudo()
        candidates = Service.search([
            ('bsi_category', 'in', categories),
            ('active', '=', True),
            ('bsi_is_custom_look', '=', False),
            ('id', 'not in', booked_ids),
        ], order='bsi_popular desc, sequence, id', limit=3)
        if not candidates:
            return {'rows': [], 'subtitle': ''}

        Recommended = request.env['bsi.enrich.data'].sudo()
        rows = [Recommended._bsi_recommended_row(s, 'FOR YOU') for s in candidates]
        subtitle = 'Because you loved %s last visit' % (
            last_service.name if last_service else booked_services[0].name)
        return {'rows': rows, 'subtitle': subtitle}
