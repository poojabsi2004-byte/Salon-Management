import random
import string

from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    bsi_loyalty_point_ids = fields.One2many(
        'bsi.salon.loyalty.point', 'bsi_partner_id', string='Loyalty Point Entries')
    bsi_loyalty_points = fields.Integer(
        string='Loyalty Points', compute='_compute_bsi_loyalty_points', store=True,
        help='Running balance — the sum of every entry below. Earned automatically: a random '
             '1-20 points once a customer\'s own appointment is completed and its invoice is '
             'fully paid, plus a 100-point bonus to whoever referred them on that same first '
             'completed, paid appointment.')
    bsi_referral_code = fields.Char(string='Referral Code', copy=False)
    bsi_referred_by_id = fields.Many2one(
        'res.partner', string='Referred By', copy=False, ondelete='set null',
        help='Set once, when this contact is first created from a booking that used someone '
             "else's referral code — never changed afterwards.")
    bsi_booking_ids = fields.One2many(
        'bsi.salon.booking.request', 'bsi_partner_id', string='Appointments',
        help='Every salon appointment booked by this customer.')
    bsi_booking_count = fields.Integer(compute='_compute_bsi_booking_count')

    @api.depends('bsi_loyalty_point_ids.bsi_points')
    def _compute_bsi_loyalty_points(self):
        for partner in self:
            partner.bsi_loyalty_points = sum(partner.bsi_loyalty_point_ids.mapped('bsi_points'))

    @api.depends('bsi_booking_ids')
    def _compute_bsi_booking_count(self):
        for partner in self:
            partner.bsi_booking_count = len(partner.bsi_booking_ids)

    def _bsi_get_or_create_referral_code(self):
        """Lazily generates a short, unique referral code the first time this contact
        actually needs one (mirrors bsi.salon.service._bsi_get_or_create_product), rather
        than generating one for every res.partner record (most of which are never a salon
        customer at all)."""
        self.ensure_one()
        if not self.bsi_referral_code:
            Partner = self.env['res.partner'].sudo()
            alphabet = string.ascii_uppercase + string.digits
            while True:
                code = ''.join(random.choices(alphabet, k=6))
                if not Partner.search_count([('bsi_referral_code', '=', code)]):
                    break
            self.sudo().bsi_referral_code = code
        return self.bsi_referral_code
