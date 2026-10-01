# -*- coding: utf-8 -*-
"""Keep the Enrich shop showing only Enrich stock.

Odoo ships its own eCommerce demo catalogue (desks, chairs, cabinets...). When
demo data is enabled those products are published, so the Enrich shop page ends
up a mix of salon retail and office furniture.

This unpublishes *only* products that were created by Odoo's own demo data --
identified through ir.model.data, so anything the client adds later is never
touched.
"""

from odoo import models

# Modules whose demo products should not appear in the Enrich shop.
_DEMO_MODULES = ('product', 'website_sale', 'sale', 'sale_management', 'stock')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def bsi_unpublish_demo_catalogue(self):
        """Unpublish Odoo's demo products; leave Enrich and client products alone."""
        data = self.env['ir.model.data'].sudo().search([
            ('model', '=', 'product.template'),
            ('module', 'in', _DEMO_MODULES),
        ])
        if not data:
            return True
        demo = self.sudo().browse(data.mapped('res_id')).exists()
        published = demo.filtered(lambda p: p.is_published)
        if published:
            published.write({'is_published': False})
        return True
