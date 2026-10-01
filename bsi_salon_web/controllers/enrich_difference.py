# -*- coding: utf-8 -*-
"""The home page's "The Enrich Difference" callouts, from backend data.

Applied by controllers/enrich_extensions.py after every other patch module, so
the anchor here must match the fully patched template (check the served page).

Was: the home page's Difference section read a fixed three-item literal --
homeDiff in the design's own render state -- icon, title and a one-line body,
with no way to add, edit, remove or reorder a callout short of re-exporting
the design.

Now: homeDiff is the active bsi.salon.difference rows (in Sequence order; see
models/bsi_enrich_difference.py), each already carrying exactly the icon/
title/body shape the design's own markup reads (`{{ d.icon }}`, `{{ d.title }}`,
`{{ d.body }}`) -- so, unlike Featured Services or Offers, no markup patch is
needed here at all, only the data literal swap. With nothing configured the
design's original three callouts render exactly as designed.
"""

import json
import logging

_logger = logging.getLogger(__name__)

# -- render state ------------------------------------------------------------

_DATA_ANCHOR = 'homeDiff: ['

# Wraps the design's own literal (kept verbatim as the fallback) -- same
# balanced-bracket swap enrich_featured.py uses for featuredServices, simpler
# here since no extra per-item field needs computing on either branch: a
# bsi.salon.difference row already matches {icon, title, body} one for one.
_DATA_HEAD = "homeDiff: ((live, design) => (live.length ? live : design))("


def _literal_end(source, open_at):
    """Index of the bracket closing the literal opened at `open_at`, or -1.

    Same balanced-bracket scan as enrich_featured._literal_end / main.py's
    _replace_value_at: the design's literal holds apostrophes (and, in other
    homeDiff-shaped literals elsewhere on the page, inlined photos), so it
    cannot be pattern-matched.
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
    """Swap the design's homeDiff literal for the live list, keeping the
    literal itself as the fallback when nothing is configured."""
    start = page.find(_DATA_ANCHOR)
    if start == -1:
        _logger.warning('Enrich site: home differentiators: render state not found, left as designed')
        return page
    open_at = start + len(_DATA_ANCHOR) - 1
    close_at = _literal_end(page, open_at)
    if close_at == -1:
        _logger.warning('Enrich site: home differentiators: design list not delimited, left as designed')
        return page
    live = json.dumps(data.get('differences') or [], ensure_ascii=False).replace('</', '<\\/')
    design = page[open_at:close_at + 1]
    return page[:start] + _DATA_HEAD + live + ', ' + design + ')' + page[close_at + 1:]


def apply(page, data):
    return _apply_data(page, data)
