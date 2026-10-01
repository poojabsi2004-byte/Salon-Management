# -*- coding: utf-8 -*-
"""Services menu offers from backend data; booking an offer books that offer.

What was hardcoded (bsi_salon_web/static/src/enrich_site.html, exported design):
the Services page's single sidebar card -- badge "FESTIVE OFFER", a fixed
sentence ("Any colour service gets a free hair spa.") and a "Book the Offer"
button that just opened the booking wizard with nothing pre-selected
(sc-camel-on-click="{{ goBookingNav }}"). Nothing about the offer -- title,
services, price -- came from the backend, and clicking it booked nothing in
particular.

Now: bsi.salon.offer (bsi_salon_backend/models/bsi_salon_offer.py) is a small
bundle-offer catalogue, same shape as bsi.salon.package. Active, published,
in-date offers (bsi.enrich.data._bsi_offers, see
bsi_salon_web/models/bsi_enrich_offers.py) replace that one static card with
one real card per offer; "Book the Offer" opens the booking wizard with the
offer's own included services pre-selected and its id carried along
(bookingOfferId), so /salon/api/booking can price and record the real offer
(see main.py's own PHASE 10 DEV comments on _bsi_resolve_selection /
_bsi_booking_quote / bsi_salon_api_booking). No offers at all: the original
static card renders exactly as designed (see SERVICE_OFFERS_DST's sc-if pair).

Applied by controllers/enrich_extensions.py after every other patch module, so
anchors here must match the fully patched template (check the served page).
"""

import logging

_logger = logging.getLogger(__name__)

# --- Services page -- the one static card becomes one real card per offer ---
#
# Unchanged as the fallback (sc-if serviceOffersEmpty below) when there are no
# active/in-date offers to show -- the page must never look empty.
_OFFER_CARD_DESIGN = (
    '<div style="border-radius:20px;padding:22px;background:#fff;border:1px solid rgba(20,17,17,.09);'
    'box-shadow:0 14px 34px -24px rgba(20,17,17,.5);">\n'
    '              <div style="font-size:10.5px;font-weight:800;letter-spacing:1.4px;color:#767676;'
    'margin-bottom:12px;">FESTIVE OFFER</div>\n'
    '              <div style="font-size:15px;font-weight:700;color:#161213;line-height:1.45;'
    'margin-bottom:14px;">Any colour service gets a free hair spa.</div>\n'
    '              <button sc-camel-on-click="{{ goBookingNav }}" style="width:100%;background:#161213;'
    'color:#fff;border:none;padding:12px;border-radius:10px;font-size:13px;font-weight:700;'
    'cursor:pointer;transition:background .2s;" style-hover="background:#e8283f;">Book the Offer</button>\n'
    '            </div>'
)

SERVICE_OFFERS_SRC = _OFFER_CARD_DESIGN
SERVICE_OFFERS_DST = (
    '<sc-if value="{{ serviceOffers.length }}" hint-placeholder-val="{{ false }}">\n'
    '            <sc-for list="{{ serviceOffers }}" as="o" hint-placeholder-count="1">\n'
    '            <div style="position:relative;border-radius:20px;padding:22px;background:#fff;'
    'border:1px solid rgba(20,17,17,.09);box-shadow:0 14px 34px -24px rgba(20,17,17,.5);'
    'margin-bottom:14px;">\n'
    '              <div style="font-size:10.5px;font-weight:800;letter-spacing:1.4px;color:#767676;'
    'margin-bottom:12px;">{{ o.badge }}</div>\n'
    '              <div style="font-size:15px;font-weight:700;color:#161213;line-height:1.45;'
    'margin-bottom:6px;">{{ o.name }}</div>\n'
    '              <sc-if value="{{ o.description }}" hint-placeholder-val="{{ false }}">\n'
    '              <div style="font-size:12.5px;color:#767676;line-height:1.5;margin-bottom:12px;">'
    '{{ o.description }}</div>\n'
    '              </sc-if>\n'
    '              <sc-if value="{{ o.serviceRows.length }}" hint-placeholder-val="{{ false }}">\n'
    '              <div style="margin-bottom:12px;">\n'
    '                <sc-for list="{{ o.serviceRows }}" as="sv3" hint-placeholder-count="2">\n'
    '                <div style="display:flex;align-items:center;gap:7px;font-size:12px;color:#454545;'
    'margin-bottom:5px;">\n'
    '                  <span style="color:#e8283f;flex-shrink:0;">✓</span><span>{{ sv3.name }}</span>\n'
    '                </div>\n'
    '                </sc-for>\n'
    '              </div>\n'
    '              </sc-if>\n'
    '              <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px;">\n'
    '                <sc-if value="{{ o.originalPrice }}" hint-placeholder-val="{{ false }}">\n'
    '                <span style="font-size:12.5px;color:#9b9093;text-decoration:line-through;">'
    '{{ o.originalPrice }}</span>\n'
    '                </sc-if>\n'
    '                <span style="font-family:\'Playfair Display\',serif;font-size:19px;color:#e8283f;">'
    '{{ o.price }}</span>\n'
    '              </div>\n'
    '              <sc-if value="{{ o.saveLabel }}" hint-placeholder-val="{{ false }}">\n'
    '              <div style="font-size:11.5px;font-weight:800;color:#1f8a4c;margin-bottom:12px;">'
    '{{ o.saveLabel }}</div>\n'
    '              </sc-if>\n'
    '              <button sc-camel-on-click="{{ o.onClick }}" style="width:100%;background:#161213;'
    'color:#fff;border:none;padding:12px;border-radius:10px;font-size:13px;font-weight:700;'
    'cursor:pointer;transition:background .2s;" style-hover="background:#e8283f;">Book the Offer</button>\n'
    '            </div>\n'
    '            </sc-for>\n'
    '            </sc-if>\n'
    '            <sc-if value="{{ serviceOffersEmpty }}" hint-placeholder-val="{{ true }}">\n'
    '            ' + _OFFER_CARD_DESIGN + '\n'
    '            </sc-if>'
)

# Render context (same place filteredServices/servicePackages are computed, chained onto
# the already-patched Packages render-context output -- see enrich_patches.py's
# PACKAGES_LIST_DST -- so this lands right alongside it).
OFFERS_CONTEXT_SRC = (
    "      servicePackages: (BSI_PACKAGES || []).map((p) => ({\n"
    "        id: p.id, name: p.name, description: p.description, price: p.price,\n"
    "        originalPrice: p.original_price, saveLabel: p.save_label,\n"
    "        serviceRows: (p.service_names || []).map((name) => ({ name })),\n"
    "        onClick: () => this.goBookingWithPackage(p.id, p.service_ids, p.price_amount, p.name),\n"
    "      })),"
)
OFFERS_CONTEXT_DST = OFFERS_CONTEXT_SRC + (
    "\n      serviceOffers: (BSI_OFFERS || []).map((o) => ({\n"
    "        id: o.id, badge: o.badge, name: o.name, description: o.description,\n"
    "        price: o.price, originalPrice: o.original_price, saveLabel: o.save_label,\n"
    "        serviceRows: (o.service_names || []).map((name) => ({ name })),\n"
    "        onClick: () => this.goBookingWithOffer(o.id, o.service_ids, o.price_amount, o.name),\n"
    "      })),\n"
    "      serviceOffersEmpty: !(BSI_OFFERS || []).length,"
)

# goBookingWithOffer: same shape as goBookingWithPackage (pre-select the offer's own
# services, reset chair/time/confirmation, clear any package selection) plus
# bookingOfferId/Name/Price so bsiBookingParams below can send offer_id with the booking.
GO_BOOKING_OFFER_SRC = (
    "  goBookingWithPackage = (packageId, serviceIds, priceAmount, name) => this.setPage('booking', { "
    "booking: { cityId: null, storeId: null, step: 1 }, selectedChairIds: [], selectedTime: null, "
    "bookingConfirmed: false, bookingPackageId: packageId, bookingPackageName: name, "
    "bookingPackagePrice: priceAmount, bookingServiceIds: (serviceIds || []).slice(), "
    "bookingServiceId: null });\n"
)
GO_BOOKING_OFFER_DST = GO_BOOKING_OFFER_SRC + (
    "  goBookingWithOffer = (offerId, serviceIds, priceAmount, name) => this.setPage('booking', { "
    "booking: { cityId: null, storeId: null, step: 1 }, selectedChairIds: [], selectedTime: null, "
    "bookingConfirmed: false, bookingOfferId: offerId, bookingOfferName: name, "
    "bookingOfferPrice: priceAmount, bookingServiceIds: (serviceIds || []).slice(), "
    "bookingServiceId: null, bookingPackageId: null, bookingPackageName: null, "
    "bookingPackagePrice: null });\n"
)

# bsiBookingParams: the offer id travels to /salon/api/booking_quote and /salon/api/booking
# exactly like package_id does -- the server (see main.py's _bsi_resolve_selection) re-reads
# and re-validates the real offer record from it rather than trusting anything else the
# client sends about it.
BOOKING_PARAMS_SRC = "      package_id: s.bookingPackageId || null,\n"
BOOKING_PARAMS_DST = BOOKING_PARAMS_SRC + "      offer_id: s.bookingOfferId || null,\n"

PATCHES = (
    ('offers render context', OFFERS_CONTEXT_SRC, OFFERS_CONTEXT_DST),
    ('offers go-booking handler', GO_BOOKING_OFFER_SRC, GO_BOOKING_OFFER_DST),
    ('offers booking params', BOOKING_PARAMS_SRC, BOOKING_PARAMS_DST),
    ('services page offer card', SERVICE_OFFERS_SRC, SERVICE_OFFERS_DST),
)


def apply(page, data):
    offers = data.get('offers') or []
    anchor = '<script type="text/x-dc"'
    tag_start = page.find(anchor)
    tag_close = page.find('>', tag_start) if tag_start != -1 else -1
    if tag_close == -1:
        _logger.warning('Enrich site: %s not found, offers catalogue not injected', anchor)
    else:
        insert_at = tag_close + 1
        injected = 'const BSI_OFFERS = %s;\n' % _js_safe(_json_dumps(offers))
        page = page[:insert_at] + injected + page[insert_at:]

    for label, source, target in PATCHES:
        if source in page:
            page = page.replace(source, target, 1)
        else:
            _logger.warning('Enrich site: %s not found, left as designed', label)
    return page


def _json_dumps(value):
    import json
    return json.dumps(value, ensure_ascii=False)


def _js_safe(dumped):
    return dumped.replace('</', r'<\/')
