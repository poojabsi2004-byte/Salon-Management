# -*- coding: utf-8 -*-
"""Home page Recommended section for the /salon site, added to bsi.enrich.data's payload.

The design's own "Recommended for you" cards are three hardcoded services with no
backend binding at all (see controllers/enrich_recommended.py). This feeds real
data in, picked in this order:

  1. Admin-curated: services with Recommended on Website ticked
     (bsi.salon.service.bsi_is_recommended), in Recommended Order.
  2. Otherwise, the catalogue's most-booked services (by how often they appear on a
     bsi.salon.booking.request), busiest first.
  3. Otherwise (an empty catalogue), 'recommended' comes back empty and the
     controller leaves the design's own three cards -- with their own photos --
     untouched, the same "never looks empty" rule every other section follows here.

A signed-in customer's own history (tier 0, ahead of all of the above) is resolved
at runtime instead -- see controllers/enrich_recommended.py's own
/salon/api/recommended route -- because the page itself is cached for every
visitor (see bsi_salon_web.controllers.main._PAGE_CACHE), so nothing specific to
one customer can be baked in here.
"""

from odoo import api, models


class BsiEnrichRecommended(models.AbstractModel):
    _inherit = 'bsi.enrich.data'

    @api.model
    def _bsi_payload(self):
        data = super()._bsi_payload()
        rows, subtitle = self._bsi_recommended()
        data['recommended'] = rows
        data['recommended_subtitle'] = subtitle
        return data

    @api.model
    def _bsi_recommended_row(self, service, badge):
        return {
            'id': service.id,
            'tag': (service.bsi_recommended_badge or '').strip() or badge,
            'name': service.name,
            'desc': service.bsi_description or service.bsi_duration or '',
            'price': service.bsi_price or '',
            'imgSrc': self._bsi_recommended_image(service),
        }

    @api.model
    def _bsi_recommended_image(self, service):
        attachment = service.bsi_image_ids[:1]
        if attachment and attachment.datas:
            return self._bsi_image_data_uri(attachment.datas)
        return service.bsi_image_url or ''

    @api.model
    def _bsi_most_booked_services(self):
        """Catalogue services ranked by how many bsi.salon.booking.request rows
        include them, busiest first. Only ever a fallback for when no service is
        curated (see _bsi_recommended)."""
        bookings = self.env['bsi.salon.booking.request'].sudo().search(
            [('bsi_service_ids', '!=', False)])
        counts = {}
        for booking in bookings:
            for service in booking.bsi_service_ids:
                if service.bsi_is_custom_look:
                    continue
                counts[service.id] = counts.get(service.id, 0) + 1
        if not counts:
            return self.env['bsi.salon.service']
        ordered_ids = sorted(counts, key=lambda sid: (-counts[sid], sid))
        return self.env['bsi.salon.service'].sudo().browse(ordered_ids).exists()

    @api.model
    def _bsi_recommended(self):
        """RECOMMENDED: ([{id, tag, name, desc, price, imgSrc}], subtitle)

        Returns ([], design's own subtitle) when neither tier has a candidate, so
        the controller's patch leaves the design's three cards exactly as designed.
        """
        Service = self.env['bsi.salon.service'].sudo()
        chosen = Service.search(
            [('bsi_is_recommended', '=', True), ('bsi_is_custom_look', '=', False),
             ('active', '=', True)],
            order='bsi_recommended_sequence, sequence, id')
        if chosen:
            rows = [self._bsi_recommended_row(s, 'RECOMMENDED') for s in chosen[:3]]
            return rows, 'Hand-picked by our artists for every guest'

        popular = self._bsi_most_booked_services().filtered('active')
        if popular:
            rows = [self._bsi_recommended_row(s, 'TRENDING') for s in popular[:3]]
            return rows, 'Loved by our regulars across every branch'

        return [], 'Because you loved Global Hair Colour last visit'

    @api.model
    def _bsi_cache_key(self):
        """Extend the version stamp with bsi.salon.booking.request -- the most-booked
        fallback's own ranking moves with new/edited bookings, which isn't covered by
        the base key's model list (bsi.salon.service itself already is, so an admin
        edit to the Recommended flag/order/badge/name/price/image already invalidates
        the cache without this)."""
        stamp = super()._bsi_cache_key()
        Booking = self.env['bsi.salon.booking.request'].sudo()
        latest = Booking.search([], order='write_date desc', limit=1)
        return stamp + '|bsi.salon.booking.request:%s:%s' % (
            Booking.search_count([]), latest.write_date or '-')
