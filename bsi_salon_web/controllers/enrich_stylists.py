# -*- coding: utf-8 -*-
"""Stylist data from the backend (stylist cards, portfolio, ratings).

Applied by controllers/enrich_extensions.py after every other patch module, so
anchors here must match the fully patched template (check the served page).

The design's STYLIST_PHOTOS/portfolio-"work" arrays are fixed sample images keyed
only by a stylist's array position -- the compiled site has no per-record photo or
portfolio slot at all. bsi.enrich.data._bsi_stylists (see
bsi_salon_web/models/bsi_enrich_stylists.py) now puts a real `photo` and
`portfolio` list on every STYLISTS row; these patches make the already-compiled
JS prefer that real data and fall back to the design's own sample art only when a
stylist has neither (so the page never looks empty for an artist with no uploads
yet).
"""

import logging

_logger = logging.getLogger(__name__)

PATCHES = (
    # Stylist grid card photo (Stylists page) -- was always STYLIST_PHOTOS[i]. STYLIST_PHOTOS
    # has only 6 sample images (the design's original hardcoded stylist count), so a 7th+
    # stylist with no uploaded photo needs the index wrapped -- otherwise STYLIST_PHOTOS[i] is
    # undefined and the card photo is simply missing (reproduced live: a 7th stylist's <img>
    # got no src at all). The other two photo patches below already wrap with % .length.
    ('stylist card photo',
     "photoSrc: STYLIST_PHOTOS[i], ",
     "photoSrc: st.photo || STYLIST_PHOTOS[i % STYLIST_PHOTOS.length], "),

    # Spotlight carousel photo (top banner on the Stylists page) -- same out-of-bounds risk
    # as the grid card photo above once there are more than 6 stylists.
    ('stylist spotlight photo',
     "src: STYLIST_PHOTOS[s.spotlightIdx],",
     "src: spot.photo || STYLIST_PHOTOS[s.spotlightIdx % STYLIST_PHOTOS.length],"),

    # Portfolio lightbox photo (opened from a stylist card's "Portfolio" button).
    ('stylist portfolio lightbox photo',
     "portfolioPhoto: STYLIST_PHOTOS[pi % STYLIST_PHOTOS.length],\n"
     "          portfolioReady: true,\n"
     "          portfolioPhotoSafe: STYLIST_PHOTOS[pi % STYLIST_PHOTOS.length],",
     "portfolioPhoto: st.photo || STYLIST_PHOTOS[pi % STYLIST_PHOTOS.length],\n"
     "          portfolioReady: true,\n"
     "          portfolioPhotoSafe: st.photo || STYLIST_PHOTOS[pi % STYLIST_PHOTOS.length],"),

    # "YOUR STYLIST" avatar on the booking confirmation ticket.
    ('booking ticket stylist photo',
     "ticketStylistPhoto: st ? STYLIST_PHOTOS[stIdx % STYLIST_PHOTOS.length] : STYLIST_PHOTOS[0],",
     "ticketStylistPhoto: st ? (st.photo || STYLIST_PHOTOS[stIdx % STYLIST_PHOTOS.length]) : STYLIST_PHOTOS[0],"),

    # Portfolio lightbox "RECENT WORK" grid -- was always the same 4 sample photos for
    # every stylist. Falls back to them only when this artist has no uploaded photos.
    ('stylist portfolio recent work',
     "const work = [",
     "const work = (st.portfolio && st.portfolio.length) "
     "? st.portfolio.map((p) => ({ src: p.src, label: p.label })) : ["),

    # Portfolio lightbox's tag chips -- the last one was always the fixed string
    # "L'Oréal trained"; show this artist's own Highlights (bsi_highlights) when set.
    ('stylist portfolio highlight tags',
     "portfolioSkills: [st.specialty, st.cat, st.years + ' yrs experience', "
     "'L\\u2019Or\\u00e9al trained'],",
     "portfolioSkills: [st.specialty, st.cat, st.years + ' yrs experience']"
     ".concat((st.highlights && st.highlights.length) ? st.highlights : ['L\\u2019Or\\u00e9al trained']),"),
)


def apply(page, data):
    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    return page
