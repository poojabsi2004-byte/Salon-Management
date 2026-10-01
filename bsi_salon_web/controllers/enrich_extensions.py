# -*- coding: utf-8 -*-
"""Per-feature patch modules, applied in this order after enrich_auth.

Each module exposes apply(page, data) -> page and owns its own PATCHES, so
separate features can be worked on without touching one shared tuple.
"""

from . import enrich_stylists
from . import enrich_portfolio_booking
from . import enrich_recommended
from . import enrich_featured
from . import enrich_offers
from . import enrich_difference

MODULES = (
    enrich_stylists,
    enrich_portfolio_booking,
    enrich_recommended,
    enrich_featured,
    enrich_offers,
    enrich_difference,
)


def apply(page, data):
    for module in MODULES:
        page = module.apply(page, data)
    return page
