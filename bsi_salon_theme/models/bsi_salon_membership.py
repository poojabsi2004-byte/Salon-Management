from odoo import models, fields


class BsiSalonMembership(models.Model):
    _name = 'bsi.salon.membership'
    _description = 'Salon Membership Tier'
    _order = 'sequence, id'

    name = fields.Char(string='Tier Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_tagline = fields.Char(string='Tagline')
    bsi_price_monthly = fields.Float(string='Monthly Price')
    bsi_price_yearly = fields.Float(string='Yearly Price (per month, billed annually)')
    bsi_perks = fields.Text(string='Perks', help='One perk per line')
    bsi_featured = fields.Boolean(string='Featured (Most Popular)')
    bsi_cta_label = fields.Char(string='Call to Action Label')
    bsi_discount_percent = fields.Float(
        string='Booking Discount %',
        help='Discount applied to a salon appointment total when the customer has an active '
             'subscription to this tier and ticks "Apply membership discount" in the booking wizard.')
    bsi_product_monthly_id = fields.Many2one('product.product', string='Monthly Product', copy=False)
    bsi_product_yearly_id = fields.Many2one('product.product', string='Yearly Product', copy=False)
    bsi_subscription_ids = fields.One2many(
        'bsi.salon.membership.subscription', 'bsi_membership_id', string='Active Users')

    def _bsi_get_or_create_product(self, billing_period):
        """Return this tier's linked product for the given billing period, creating a simple
        service product on the fly the first time it's needed (mirrors
        bsi.salon.service._bsi_get_or_create_product) so a tier is always purchasable without
        having to pre-configure a product by hand."""
        self.ensure_one()
        field_name = 'bsi_product_monthly_id' if billing_period == 'monthly' else 'bsi_product_yearly_id'
        if not self[field_name]:
            # bsi_price_yearly is "per month, billed annually" — the sellable product must
            # charge the full annual amount, not the per-month display figure.
            price = self.bsi_price_monthly if billing_period == 'monthly' else self.bsi_price_yearly * 12
            product = self.env['product.product'].sudo().create({
                'name': '%s Membership — %s' % (self.name, 'Monthly' if billing_period == 'monthly' else 'Yearly'),
                'type': 'service',
                'list_price': price,
                'sale_ok': True,
                'purchase_ok': False,
                'website_published': True,
            })
            self.sudo()[field_name] = product.id
        return self[field_name]
