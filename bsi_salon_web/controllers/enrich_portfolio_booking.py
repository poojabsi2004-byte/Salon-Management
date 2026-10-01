# -*- coding: utf-8 -*-
"""Booking from a stylist's portfolio books that stylist.

Applied by controllers/enrich_extensions.py after every other patch module, so
anchors here must match the fully patched template (check the served page).

Bug fixed here: the Stylists page's three "Book" entry points all look alike
but only two of them actually carried the artist through --

* the stylist card's own "Book {name}" button (onBookWith -> bookWithStylist(i))
* the portfolio lightbox's "Book with {name}" button (portfolioBook -> bookWithStylist(pi))

-- both correctly seed bookingStylist (-> bsiBookingParams' artist_id -> the
lead's bsi_artist_id, see main.py's bsi_salon_api_booking). The big Spotlight
hero card above the grid is a third, equally prominent "Book with {name}"
button that instead called the generic goBookingNav() reset, so a visitor who
opened/booked straight from the Spotlight silently got a bookingless -- no
artist at all -- lead, even though the button named a specific stylist.
Spotlight's own click handler (spotBookWith) now routes through the exact
same bookWithStylist(i) the other two entry points already use.
"""

import logging

_logger = logging.getLogger(__name__)

# The Spotlight hero's own click handler, added next to its sibling spotNext
# so it has access to the same `s` (state) closure spotNext already uses.
_SPOT_BOOK_WITH_SRC = (
    "      spotNext: () => this.setState((p) => ({ spotlightIdx: (p.spotlightIdx + 1) "
    "% STYLISTS.length })),\n"
)
_SPOT_BOOK_WITH_DST = (
    "      spotNext: () => this.setState((p) => ({ spotlightIdx: (p.spotlightIdx + 1) "
    "% STYLISTS.length })),\n"
    "      spotBookWith: () => this.bookWithStylist(s.spotlightIdx),\n"
)

# The Spotlight hero's "Book with {name}" button -- was wired to the generic
# goBookingNav (plain reset to step 1, no artist), now to the handler above.
_SPOT_BUTTON_SRC = (
    '<button sc-camel-on-click="{{ goBookingNav }}" style="background:#e8283f;color:#fff;'
    'border:none;padding:14px 28px;border-radius:10px;font-size:14px;font-weight:700;'
    'cursor:pointer;box-shadow:0 14px 30px -14px rgba(232,40,63,.9);'
    'transition:transform .2s;" style-hover="transform:translateY(-2px);">'
    'Book with {{ spotFirstName }} →</button>'
)
_SPOT_BUTTON_DST = (
    '<button sc-camel-on-click="{{ spotBookWith }}" style="background:#e8283f;color:#fff;'
    'border:none;padding:14px 28px;border-radius:10px;font-size:14px;font-weight:700;'
    'cursor:pointer;box-shadow:0 14px 30px -14px rgba(232,40,63,.9);'
    'transition:transform .2s;" style-hover="transform:translateY(-2px);">'
    'Book with {{ spotFirstName }} →</button>'
)

PATCHES = (
    ('stylist spotlight: book-with handler', _SPOT_BOOK_WITH_SRC, _SPOT_BOOK_WITH_DST),
    ('stylist spotlight: book-with button', _SPOT_BUTTON_SRC, _SPOT_BUTTON_DST),
)


def apply(page, data):
    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    return page
