# -*- coding: utf-8 -*-
"""Featured services from backend data.

Applied by controllers/enrich_extensions.py after every other patch module, so
anchors here must match the fully patched template (check the served page).

Was: the home page's "Featured Services" grid read a fixed four-card literal
(featuredServices in the page's render state) -- name, one-line blurb, price
label and an inlined photo -- with no duration and no way to book from a card.

Now: the cards are the services ticked "Featured on Website" in the backend
(data['featured_services'], see models/bsi_enrich_featured.py), in Featured
Order, each with its own price, duration, description, "POPULAR" badge and
photo, and a Book button that opens the booking with that service selected
(goBookingWithService, the Services page's own entry point). A featured service
with no photo reuses the design's photo for that position. With nothing
featured the design's four cards stay, their Book buttons picking the catalogue
service of the same name when there is one.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# -- render state ----------------------------------------------------------

_DATA_ANCHOR = 'featuredServices: ['

# Wraps the design's own literal (kept verbatim as the fallback) -- see apply().
_DATA_HEAD = (
    "featuredServices: ((live, design) => {\n"
    "        const all = [].concat.apply([], Object.keys(SERVICES_DATA || {}).map((k) => SERVICES_DATA[k] || []));\n"
    "        const rows = live.length\n"
    "          ? live.map((f, i) => ({ ...f, imgSrc: f.imgSrc || (design[i % design.length] || {}).imgSrc || '' }))\n"
    "          : design.map((f) => {\n"
    "              const m = all.find((x) => String(x.name || '').toLowerCase() === String(f.name || '').toLowerCase());\n"
    "              return { ...f, id: m ? m.id : null, duration: (m && m.duration) || '', badge: '' };\n"
    "            });\n"
    "        return rows.map((f) => ({\n"
    "          ...f, hasBadge: !!f.badge, hasDuration: !!f.duration,\n"
    "          bookLabel: 'Book now', bookAria: 'Book ' + (f.name || 'this service'),\n"
    "          onBook: () => ((f.id && this.goBookingWithService)\n"
    "            ? this.goBookingWithService(f.id, f.name) : this.goBookingNav()),\n"
    "        }));\n"
    "      })("
)

# -- card markup -------------------------------------------------------------

_CARD_SRC = (
    '<div data-tilt="" style="border:1px solid rgba(20,17,17,.08);border-radius:18px;'
    'overflow:hidden;background:#ffffff;box-shadow:0 4px 20px rgba(20,17,17,.05);'
    'transition:box-shadow .25s,transform .25s;" style-hover="box-shadow:0 18px 40px -14px '
    'rgba(20,17,17,.28);transform:translateY(-5px);">\n'
    '            <div style="position:relative;height:150px;overflow:hidden;">\n'
    '              <img src="{{ f.imgSrc }}" alt="{{ f.name }}" style="width:100%;height:150px;'
    'object-fit:cover;display:block;background:#241b1e;">\n'
    '              <div style="position:absolute;inset:0;background:linear-gradient(180deg,'
    'rgba(22,18,19,.05),rgba(22,18,19,.45));"></div>\n'
    '              <div style="position:absolute;bottom:10px;left:14px;font-family:\'Playfair '
    'Display\',serif;color:#fff;font-size:17px;">{{ f.name }}</div>\n'
    '            </div>\n'
    '            <div style="padding:18px 22px 22px;">\n'
    '              <div style="font-size:13px;color:#767676;margin-bottom:14px;line-height:1.55;">'
    '{{ f.desc }}</div>\n'
    '              <div style="font-size:14px;color:#161213;font-weight:700;">{{ f.price }}</div>\n'
    '            </div>\n'
    '          </div>'
)

# Same card, laid out as a column so every Book button lines up at the bottom of
# its row; badge styled like the Recommended cards' tag, button in ink/crimson.
_CARD_DST = (
    '<div data-tilt="" class="bsi-feat-card" style="border:1px solid rgba(20,17,17,.08);'
    'border-radius:18px;overflow:hidden;background:#ffffff;box-shadow:0 4px 20px rgba(20,17,17,.05);'
    'transition:box-shadow .25s,transform .25s;display:flex;flex-direction:column;" '
    'style-hover="box-shadow:0 18px 40px -14px rgba(20,17,17,.28);transform:translateY(-5px);">\n'
    '            <div style="position:relative;height:150px;overflow:hidden;flex-shrink:0;">\n'
    '              <img src="{{ f.imgSrc }}" alt="{{ f.name }}" style="width:100%;height:150px;'
    'object-fit:cover;display:block;background:#241b1e;">\n'
    '              <div style="position:absolute;inset:0;background:linear-gradient(180deg,'
    'rgba(22,18,19,.05),rgba(22,18,19,.45));"></div>\n'
    '              <sc-if value="{{ f.hasBadge }}" hint-placeholder-val="{{ false }}">\n'
    '                <div class="bsi-feat-badge" style="position:absolute;top:12px;left:12px;'
    'font-size:10.5px;color:#fff;font-weight:800;letter-spacing:.8px;background:#e8283f;'
    'padding:4px 10px;border-radius:999px;">{{ f.badge }}</div>\n'
    '              </sc-if>\n'
    '              <div style="position:absolute;bottom:10px;left:14px;right:14px;font-family:\'Playfair '
    'Display\',serif;color:#fff;font-size:17px;">{{ f.name }}</div>\n'
    '            </div>\n'
    '            <div style="padding:18px 22px 22px;flex:1;display:flex;flex-direction:column;">\n'
    '              <div class="bsi-feat-desc" style="font-size:13px;color:#767676;margin-bottom:14px;'
    'line-height:1.55;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;'
    'overflow:hidden;">{{ f.desc }}</div>\n'
    '              <div style="margin-top:auto;display:flex;justify-content:space-between;'
    'align-items:baseline;gap:10px;flex-wrap:wrap;">\n'
    '                <div style="font-size:14px;color:#161213;font-weight:700;">{{ f.price }}</div>\n'
    '                <sc-if value="{{ f.hasDuration }}" hint-placeholder-val="{{ false }}">\n'
    '                  <div class="bsi-feat-duration" style="font-size:12px;color:#767676;'
    'font-weight:600;">{{ f.duration }}</div>\n'
    '                </sc-if>\n'
    '              </div>\n'
    '              <button type="button" class="bsi-feat-book" sc-camel-on-click="{{ f.onBook }}" '
    'aria-label="{{ f.bookAria }}" style="margin-top:14px;width:100%;background:#161213;'
    'color:#fdf3ea;border:none;padding:11px 14px;border-radius:10px;font-size:13px;font-weight:700;'
    'cursor:pointer;transition:background .2s,transform .2s;" style-hover="background:#e8283f;'
    'transform:translateY(-1px);">{{ f.bookLabel }} →</button>\n'
    '            </div>\n'
    '          </div>'
)

PATCHES = (
    ('featured services: card with badge, duration and Book button', _CARD_SRC, _CARD_DST),
)


def _literal_end(source, open_at):
    """Index of the bracket closing the literal opened at `open_at`, or -1.

    Same balanced-bracket scan as main._replace_value_at: the design's literal
    holds inlined photos and apostrophes, so it cannot be pattern-matched.
    """
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
                return index
        index += 1
    return -1


def _apply_data(page, data):
    """Swap the design's featuredServices literal for the live list, keeping the
    literal itself as the fallback (and the photo source for photo-less cards)."""
    start = page.find(_DATA_ANCHOR)
    if start == -1:
        _logger.warning('Enrich site: featured services: render state not found, left as designed')
        return page
    open_at = start + len(_DATA_ANCHOR) - 1
    close_at = _literal_end(page, open_at)
    if close_at == -1:
        _logger.warning('Enrich site: featured services: design list not delimited, left as designed')
        return page
    live = json.dumps(data.get('featured_services') or [], ensure_ascii=False).replace('</', '<\\/')
    design = page[open_at:close_at + 1]
    return page[:start] + _DATA_HEAD + live + ', ' + design + ')' + page[close_at + 1:]


def apply(page, data):
    page = _apply_data(page, data)
    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    return page
