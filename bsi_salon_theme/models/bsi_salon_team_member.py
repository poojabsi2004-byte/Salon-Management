from odoo import models, fields, api


class BsiSalonTeamMember(models.Model):
    _name = 'bsi.salon.team.member'
    _description = 'Salon Team Member'
    _order = 'sequence, id'

    name = fields.Char(string='Full Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_role = fields.Char(string='Role')
    bsi_specialty = fields.Char(string='Specialty')
    bsi_since_year = fields.Char(string='Since Year')
    bsi_image = fields.Image(string='Photo', max_width=1024, max_height=1024)
    bsi_image_url = fields.Char(string='Photo URL')
    bsi_location_id = fields.Many2one(
        'bsi.salon.location', string='Base Branch',
        help='Branch this artist normally works at. Used to filter the artist options on an '
             'appointment once a branch is selected (artists without a branch stay available '
             'everywhere).')
    bsi_charge_amount = fields.Float(
        string='Artist Surcharge (₹)', default=0.0,
        help='Flat amount (in ₹) added to the total when this artist is assigned to an '
             'appointment, e.g. 200 for a senior stylist premium.')
    bsi_surcharge_product_id = fields.Many2one(
        'product.product', string='Linked Surcharge Product',
        help='Product used for this artist\'s surcharge line on a quotation/sale order. '
             'Created automatically the first time it\'s needed if left empty.')
    bsi_is_available_now = fields.Boolean(
        string='Available Now', compute='_compute_bsi_is_available_now',
        search='_search_bsi_is_available_now',
        help='False as soon as this artist has a Draft, Started or Ended appointment '
             'booked for TODAY — freed up again once that appointment is Cancelled or Done, '
             'or once its booking date is in the past/future — never stored, always '
             'computed fresh.')
    bsi_booking_ids = fields.One2many(
        'bsi.salon.booking.request', 'bsi_artist_id', string='Appointments',
        help='Every appointment this artist has ever been assigned to.')
    bsi_booking_count = fields.Integer(compute='_compute_bsi_booking_count')

    @api.depends('bsi_booking_ids')
    def _compute_bsi_booking_count(self):
        for member in self:
            member.bsi_booking_count = len(member.bsi_booking_ids)

    @api.depends()
    def _compute_bsi_is_available_now(self):
        # Not keyed off any field of THIS model — it depends on the live state of other
        # artists' appointments elsewhere, so there's nothing on this record itself to
        # @api.depends on; always recomputed fresh on every read instead.
        # Must also be scoped to TODAY's booking date — otherwise a future (or past) Draft
        # appointment would flag the artist as permanently "Booked" even with nothing on
        # their plate today.
        Appointment = self.env['bsi.salon.booking.request'].sudo()
        today = fields.Date.context_today(self)
        busy_ids = set(Appointment.search([
            ('bsi_state', 'not in', ('cancelled', 'completed')),
            ('bsi_preferred_date', '=', today),
        ]).mapped('bsi_artist_id.id'))
        for member in self:
            member.bsi_is_available_now = member.id not in busy_ids

    def _search_bsi_is_available_now(self, operator, value):
        # Lets "Available Now" be used as a real search filter (see the Team Member search
        # view and the Salon Dashboard's "Available Staff" KPI card) even though it's a
        # never-stored, always-fresh compute — translates straight into the same busy-id
        # lookup the compute itself uses above.
        # Odoo normalizes a Boolean leaf like ('field', '=', True) into ('field', 'in',
        # OrderedSet([True])) before this is called — operator isn't reliably '=' and value
        # isn't reliably a plain bool, so both are handled generically here rather than
        # assumed.
        today = fields.Date.context_today(self)
        busy_ids = self.env['bsi.salon.booking.request'].sudo().search([
            ('bsi_state', 'not in', ('cancelled', 'completed')),
            ('bsi_preferred_date', '=', today),
        ]).mapped('bsi_artist_id.id')
        values = [value] if isinstance(value, bool) else list(value)
        wants_true = any(values)
        if operator in ('!=', 'not in'):
            wants_true = not wants_true
        return [('id', 'not in' if wants_true else 'in', busy_ids)]

    def _bsi_get_or_create_surcharge_product(self):
        """Return this artist's linked surcharge product, creating a simple service product
        on the fly the first time it's needed so the flat charge can always be quoted as its
        own order line (see bsi.salon.booking.request._bsi_create_quotation)."""
        self.ensure_one()
        if not self.bsi_surcharge_product_id:
            product = self.env['product.product'].sudo().create({
                'name': '%s - Artist Surcharge' % self.name,
                'type': 'service',
                'list_price': self.bsi_charge_amount,
                'sale_ok': True,
                'purchase_ok': False,
            })
            self.sudo().bsi_surcharge_product_id = product.id
        return self.bsi_surcharge_product_id
