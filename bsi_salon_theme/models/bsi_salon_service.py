import re

from odoo import models, fields


class BsiSalonService(models.Model):
    _name = 'bsi.salon.service'
    _description = 'Salon Service'
    _order = 'sequence, id'

    name = fields.Char(string='Service Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_category = fields.Selection(
        [('hair', 'Hair'), ('colour', 'Colour'), ('nails', 'Nails'),
         ('skin', 'Skin'), ('body', 'Body'), ('bridal', 'Bridal')],
        string='Category', required=True, default='hair')
    bsi_description = fields.Text(string='Description')
    bsi_price = fields.Char(string='Price Label', help='Display label, e.g. "£55" or "From £250"')
    bsi_duration = fields.Char(string='Duration Label', help='Display label, e.g. "60 min"')
    bsi_popular = fields.Boolean(string='Popular')
    bsi_image_url = fields.Char(string='Image URL')
    bsi_image_ids = fields.Many2many('ir.attachment', string='Images')
    bsi_price_amount = fields.Float(
        string='Price Amount', help='Numeric price (company currency) used to calculate '
                                     'appointment totals and quotation/sale order lines.')
    bsi_product_id = fields.Many2one(
        'product.product', string='Linked Product',
        help='Product used when this service is added to an appointment quotation/sale order. '
             'Created automatically the first time this service is quoted if left empty.')

    def _bsi_parse_price_label(self):
        """Best-effort numeric price extracted from the display label (e.g. "From ₹499" -> 499.0),
        used as a fallback when Price Amount hasn't been filled in for an existing service."""
        self.ensure_one()
        if not self.bsi_price:
            return 0.0
        match = re.search(r'[\d,]+(?:\.\d+)?', self.bsi_price)
        if not match:
            return 0.0
        try:
            return float(match.group(0).replace(',', ''))
        except ValueError:
            return 0.0

    def _bsi_get_effective_price(self):
        self.ensure_one()
        return self.bsi_price_amount or self._bsi_parse_price_label()

    def _bsi_get_or_create_product(self):
        """Return this service's linked product, creating a simple service product on the fly
        the first time it's needed so every selected service can always be quoted."""
        self.ensure_one()
        if not self.bsi_product_id:
            product = self.env['product.product'].sudo().create({
                'name': self.name,
                'type': 'service',
                'list_price': self._bsi_get_effective_price(),
                'sale_ok': True,
                'purchase_ok': False,
            })
            self.sudo().bsi_product_id = product.id
        return self.bsi_product_id
