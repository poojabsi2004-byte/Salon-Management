# -*- coding: utf-8 -*-
"""Featured services for the /salon site, added to bsi.enrich.data's payload.

The home page's "Featured Services" cards (controllers/enrich_featured.py) show
the active services ticked "Featured on Website" (bsi.salon.service
bsi_is_featured), in Featured Order (bsi_featured_sequence). Each card carries
the service's own name, price, duration, description and image, plus its id so
its Book button opens the booking with that service selected.

No featured service: the payload is empty and the design's four cards stay.
"""

import base64
import binascii
import logging

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools.image import image_process

_logger = logging.getLogger(__name__)

# Two rows of the design's four-column grid.
_FEATURED_LIMIT = 8

# Card photos are 150 px tall in a ~300 px column, so this is plenty even on a
# high-density screen, and keeps an uploaded multi-megabyte photo from bloating
# the (cached, shared) page.
_FEATURED_IMAGE_SIZE = (800, 800)


class BsiEnrichFeatured(models.AbstractModel):
    _inherit = 'bsi.enrich.data'

    @api.model
    def _bsi_featured_records(self):
        """Featured, active catalogue services in their home page order."""
        return self.env['bsi.salon.service'].sudo().search(
            [('bsi_is_featured', '=', True), ('bsi_is_custom_look', '=', False)],
            order='bsi_featured_sequence, sequence, id', limit=_FEATURED_LIMIT)

    @api.model
    def _bsi_featured_image(self, service):
        """The card photo: the newest uploaded image, else the Image URL, else ''
        (the page then reuses the design's photo for that position)."""
        attachment = service.bsi_image_ids.filtered(
            lambda att: (att.mimetype or '').startswith('image/') and att.datas)[:1]
        if attachment:
            if attachment.mimetype == 'image/svg+xml':
                return 'data:image/svg+xml;base64,%s' % attachment.datas.decode('ascii')
            try:
                resized = image_process(
                    base64.b64decode(attachment.datas), size=_FEATURED_IMAGE_SIZE,
                    quality=85, output_format='JPEG')
            except (UserError, ValueError, binascii.Error) as error:
                _logger.warning('Enrich site: featured image of service %s unreadable: %s',
                                service.id, error)
                resized = False
            if resized:
                return self._bsi_image_data_uri(base64.b64encode(resized))
        return service.bsi_image_url or ''

    @api.model
    def _bsi_featured_price(self, service, currency):
        """The service's own price label, else its Price Amount in the company currency."""
        if service.bsi_price:
            return service.bsi_price
        if not service.bsi_price_amount:
            return ''
        amount = '{:,.0f}'.format(service.bsi_price_amount)
        symbol = currency.symbol or ''
        if currency.position == 'after':
            return '%s %s' % (amount, symbol)
        return '%s%s' % (symbol, amount)

    @api.model
    def _bsi_featured_services(self):
        """BSI_FEATURED: [{id, name, desc, price, duration, badge, imgSrc}]"""
        currency = self.env['res.company'].sudo()._bsi_brand_company().currency_id
        rows = []
        for service in self._bsi_featured_records():
            rows.append({
                'id': service.id,
                'name': service.name,
                'desc': (service.bsi_description or '').strip(),
                'price': self._bsi_featured_price(service, currency),
                'duration': service.bsi_duration or '',
                'badge': 'POPULAR' if service.bsi_popular else '',
                'imgSrc': self._bsi_featured_image(service),
            })
        return rows

    @api.model
    def _bsi_payload(self):
        data = super()._bsi_payload()
        data['featured_services'] = self._bsi_featured_services()
        return data

    @api.model
    def _bsi_cache_key(self):
        """Rebuild the page when a service is featured/unfeatured, reordered or edited,
        or when one of its images is replaced."""
        key = super()._bsi_cache_key()
        services = self._bsi_featured_records()
        images = services.bsi_image_ids.sorted('write_date')[-1:]
        stamp = ','.join(
            '%s:%s:%s' % (service.id, service.bsi_featured_sequence, service.write_date or '-')
            for service in services)
        return '%s|featured:%s|featured_img:%s:%s' % (
            key, stamp, len(services.bsi_image_ids), images.write_date or '-')
