# -*- coding: utf-8 -*-
"""Services menu offers for the /salon site, added to bsi.enrich.data's payload.

Only active, published, in-date bsi.salon.offer records are exposed here (see
bsi.salon.offer._bsi_is_bookable, the exact same test) -- an archived,
unpublished or out-of-date offer simply does not appear in BSI_OFFERS, and the
Services page (controllers/enrich_offers.py) falls back to the design's own
single "FESTIVE OFFER" card whenever this list is empty, so the page never
looks empty.
"""

from odoo import api, fields, models


class BsiEnrichOffers(models.AbstractModel):
    _inherit = 'bsi.enrich.data'

    @api.model
    def _bsi_offers(self):
        """BSI_OFFERS: [{id, badge, name, description, price, original_price, save_label,
        price_amount, service_ids, service_names, image}]"""
        today = fields.Date.context_today(self)
        Offer = self.env['bsi.salon.offer'].sudo()
        domain = [
            ('bsi_website_published', '=', True),
            '|', ('bsi_date_from', '=', False), ('bsi_date_from', '<=', today),
            '|', ('bsi_date_to', '=', False), ('bsi_date_to', '>=', today),
        ]
        offers = Offer.search(domain, order='sequence, id')
        rows = []
        for offer in offers:
            services = offer.bsi_service_ids
            rows.append({
                'id': offer.id,
                'badge': offer.bsi_badge or 'OFFER',
                'name': offer.name,
                'description': offer.bsi_description or '',
                'price': offer.bsi_offer_price or '',
                'original_price': offer.bsi_original_price or '',
                'save_label': offer.bsi_save_label or '',
                'price_amount': offer._bsi_get_effective_price(),
                'service_ids': services.ids,
                'service_names': services.mapped('name'),
                'image': self._bsi_image_data_uri(offer.bsi_image) if offer.bsi_image else '',
            })
        return rows

    @api.model
    def _bsi_payload(self):
        data = super()._bsi_payload()
        data['offers'] = self._bsi_offers()
        return data

    @api.model
    def _bsi_cache_key(self):
        """Rebuild the page when an offer is added/archived/edited, published/unpublished,
        or its validity window changes -- every one of those changes write_date, so the
        write_date/count stamp below catches all of them, the same way _bsi_packages'
        own stamp does for bsi.salon.package."""
        key = super()._bsi_cache_key()
        Offer = self.env['bsi.salon.offer'].sudo()
        latest = Offer.with_context(active_test=False).search(
            [], order='write_date desc', limit=1)
        return '%s|offers:%s:%s' % (
            key, Offer.with_context(active_test=False).search_count([]),
            latest.write_date or '-')
