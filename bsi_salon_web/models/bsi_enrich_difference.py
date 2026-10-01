# -*- coding: utf-8 -*-
""""The Enrich Difference" home page callouts, added to bsi.enrich.data's payload.

The home page's Difference section (controllers/enrich_difference.py) shows a
short list of icon + title + one-line body callouts (homeDiff in the design's
own render state). This provider reads the active, published rows of
bsi.salon.difference (bsi_salon_backend/models/bsi_salon_phase2_content.py), in
Sequence order, in exactly the shape the design already expects.

No differentiators configured: the payload is empty and the design's original
three callouts stay (see enrich_difference.apply).
"""

from odoo import api, models


class BsiEnrichDifference(models.AbstractModel):
    _inherit = 'bsi.enrich.data'

    @api.model
    def _bsi_difference_items(self):
        """BSI_DIFFERENCE: [{icon, title, body}]"""
        rows = self.env['bsi.salon.difference'].sudo().search([], order='sequence, id')
        return [{
            'icon': row.bsi_icon or '',
            'title': row.name,
            'body': row.bsi_description or '',
        } for row in rows]

    @api.model
    def _bsi_payload(self):
        data = super()._bsi_payload()
        data['differences'] = self._bsi_difference_items()
        return data

    @api.model
    def _bsi_cache_key(self):
        """Rebuild the page when a differentiator is added/edited, reordered,
        or published/unpublished -- all of which touch write_date, same as
        enrich_offers._bsi_cache_key does for bsi.salon.offer."""
        key = super()._bsi_cache_key()
        Difference = self.env['bsi.salon.difference'].sudo()
        all_rows = Difference.with_context(active_test=False).search(
            [], order='write_date desc', limit=1)
        return '%s|difference:%s:%s' % (
            key, Difference.with_context(active_test=False).search_count([]),
            all_rows.write_date or '-')
