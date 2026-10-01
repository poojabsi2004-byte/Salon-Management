# -*- coding: utf-8 -*-
"""Home page banner, "LIVE right now" strip and services marquee: live data.

Content only -- every style, animation and click handler of the design is kept;
only the words and numbers now come from the backend (see
models/bsi_enrich_hero.py for where each value comes from):

  * badge, two-line headline, rotating lines and the two button labels:
    About Page record > Home Banner tab (design copy when blank);
  * services marquee: the active service catalogue, in backend order;
  * live strip: real figures, baked in at build time and refreshed at runtime
    from /salon/api/live_pulse (the page itself is cached until catalogue data
    changes, but these move minute by minute).

Applied by BsiSalonWeb._build_site after every other template patch, so the
anchors below match the fully patched template. A missing anchor only logs
"not found, left as designed" and that part keeps the design's own copy.
"""

import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def _js_safe(dumped):
    return dumped.replace('</', r'<\/')


# --- markup ------------------------------------------------------------------

BADGE_SRC = '          PREMIUM SALON CHAIN · 100+ LOCATIONS\n'
BADGE_DST = '          {{ heroBadge }}\n'

TITLE_SRC = (
    '          Your beauty,<br>\n'
    '          <span style="position:relative;display:inline-block;color:#e8283f;">\n'
    '            enriched.\n'
)
TITLE_DST = (
    '          {{ heroTitle1 }}<br>\n'
    '          <span style="position:relative;display:inline-block;color:#e8283f;">\n'
    '            {{ heroTitle2 }}\n'
)

BOOK_SRC = (
    '            Book an Appointment\n'
    '            <span style="position:absolute;top:0;bottom:0;width:40%;'
)
BOOK_DST = (
    '            {{ heroBookLabel }}\n'
    '            <span style="position:absolute;top:0;bottom:0;width:40%;'
)

STORES_SRC = 'style-hover="background:rgba(255,255,255,.14);border-color:#fdf3ea;">Find a Store</button>'
STORES_DST = 'style-hover="background:rgba(255,255,255,.14);border-color:#fdf3ea;">{{ heroStoresLabel }}</button>'

# The lap length now follows the catalogue, so the duration does too (same speed).
MARQUEE_DUR_SRC = '<div style="display:flex;gap:44px;width:max-content;animation:marqueeL 28s linear infinite;">'
MARQUEE_DUR_DST = '<div style="display:flex;gap:44px;width:max-content;animation:marqueeL {{ marqueeDur }}s linear infinite;">'

# --- render context ----------------------------------------------------------

CONTEXT_SRC = "      heroHeadline: this.props.heroHeadline || 'Your Beauty, Enriched.',\n"
CONTEXT_DST = CONTEXT_SRC + (
    "      heroBadge: BSI_HERO.badge, heroTitle1: BSI_HERO.title1, heroTitle2: BSI_HERO.title2,\n"
    "      heroBookLabel: BSI_HERO.bookLabel, heroStoresLabel: BSI_HERO.storesLabel,\n"
    "      marqueeDur: BSI_HERO.marqueeDur,\n"
)

WORDS_SRC = (
    "      bannerWords: [\n"
    "        { label: 'Precision cuts by master artists', delay: 0 },\n"
    "        { label: 'Global colour with L\\u2019Or\\u00e9al Professionnel', delay: 3 },\n"
    "        { label: 'Skin rituals that actually work', delay: 6 },\n"
    "        { label: 'Bridal artistry for your biggest day', delay: 9 },\n"
    "      ],\n"
)
WORDS_DST = "      bannerWords: BSI_HERO.words,\n"

MARQUEE_SRC = (
    "        const items = ['Haircut & Style', 'Global Colour', 'Keratin Treatment', 'Hair Spa', "
    "'Bridal Makeup', 'HD Makeup', 'Nail Art', 'Classic Facial', 'Manicure', 'Pedicure', "
    "'Threading', 'Blowout'];\n"
    "        return items.concat(items).map((label) => ({ label }));\n"
)
MARQUEE_DST = (
    "        const items = BSI_HERO.marquee;\n"
    "        return items.concat(items).map((label) => ({ label }));\n"
)

PULSE_SRC = (
    "      pulseFacts: [\n"
    "        { value: '17', label: 'chairs occupied across the city right now' },\n"
    "        { value: '3 min', label: 'wait at Satellite \\u2014 your nearest branch' },\n"
    "        { value: '9', label: 'artists free in the next hour' },\n"
    "        { value: '42', label: 'appointments booked today' },\n"
    "      ].map("
)
PULSE_DST = "      pulseFacts: (s.bsiLivePulse || BSI_HERO.pulse).map("

# --- runtime refresh of the live strip ---------------------------------------

MOUNT_SRC = (
    "    this._pulseTimer = setInterval(() => this.setState((s) => "
    "({ pulseIdx: (s.pulseIdx + 1) % 4 })), 3600);\n"
)
MOUNT_DST = MOUNT_SRC + (
    "    this._bsiLoadPulse = () => {\n"
    "      if (document.hidden) { return; }\n"
    "      fetch('/salon/api/live_pulse', { method: 'POST', credentials: 'same-origin', "
    "headers: { 'Content-Type': 'application/json' }, "
    "body: JSON.stringify({ id: 1, jsonrpc: '2.0', method: 'call', params: {} }) })\n"
    "        .then((r) => r.json()).then((payload) => {\n"
    "          const rows = payload && payload.result;\n"
    "          if (Array.isArray(rows) && rows.length === 4) { this.setState({ bsiLivePulse: rows }); }\n"
    "        }).catch(function () {});\n"
    "    };\n"
    "    this._bsiLoadPulse();\n"
    "    this._bsiPulseRefresh = setInterval(this._bsiLoadPulse, 60000);\n"
)

UNMOUNT_SRC = "    if (this._pulseTimer) clearInterval(this._pulseTimer);\n"
UNMOUNT_DST = UNMOUNT_SRC + "    if (this._bsiPulseRefresh) clearInterval(this._bsiPulseRefresh);\n"

PATCHES = (
    ('hero badge', BADGE_SRC, BADGE_DST),
    ('hero headline', TITLE_SRC, TITLE_DST),
    ('hero booking button', BOOK_SRC, BOOK_DST),
    ('hero stores button', STORES_SRC, STORES_DST),
    ('services marquee speed', MARQUEE_DUR_SRC, MARQUEE_DUR_DST),
    ('hero render context', CONTEXT_SRC, CONTEXT_DST),
    ('hero rotating lines', WORDS_SRC, WORDS_DST),
    ('services marquee', MARQUEE_SRC, MARQUEE_DST),
    ('live strip facts', PULSE_SRC, PULSE_DST),
    ('live strip refresh', MOUNT_SRC, MOUNT_DST),
    ('live strip refresh cleanup', UNMOUNT_SRC, UNMOUNT_DST),
)


def apply(page, data):
    """Inject BSI_HERO and point the banner, strip and marquee at it."""
    hero = data.get('hero')
    if not hero:
        return page
    anchor = '<script type="text/x-dc"'
    tag_start = page.find(anchor)
    tag_close = page.find('>', tag_start) if tag_start != -1 else -1
    if tag_close == -1:
        _logger.warning('Enrich site: %s not found, home banner left as designed', anchor)
        return page
    insert_at = tag_close + 1
    page = page[:insert_at] + 'const BSI_HERO = %s;\n' % _js_safe(
        json.dumps(hero, ensure_ascii=False)) + page[insert_at:]

    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    return page


class BsiSalonHeroApi(http.Controller):

    @http.route('/salon/api/live_pulse', type='jsonrpc', auth='public', website=True)
    def bsi_salon_api_live_pulse(self, **kwargs):
        """The home page's "LIVE right now" facts, fresh (the page itself is cached)."""
        return request.env['bsi.enrich.data'].sudo()._bsi_live_pulse()
