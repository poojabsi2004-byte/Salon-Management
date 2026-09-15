from odoo import models, fields, api, _


class BsiSalonLoyaltyPoint(models.Model):
    _name = 'bsi.salon.loyalty.point'
    _description = 'Salon Loyalty Point Ledger Entry'
    _order = 'create_date desc'

    bsi_partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True, ondelete='cascade')
    bsi_points = fields.Integer(string='Points', required=True)
    bsi_reason = fields.Selection(
        [('appointment', 'Booking Completed'), ('referral', 'Referral Bonus')],
        string='Reason', required=True)
    bsi_appointment_id = fields.Many2one(
        'bsi.salon.booking.request', string='Booking', ondelete='set null',
        help='The completed, paid appointment this entry rewards — the referring '
             "customer's own appointment for an 'Appointment Completed' entry, or the "
             "referred friend's for a 'Referral Bonus' one.")
    bsi_referred_partner_id = fields.Many2one(
        'res.partner', string='Referred Friend', ondelete='set null',
        help='Set only on a Referral Bonus entry — the new customer whose first completed, '
             'paid appointment earned this bonus for bsi_partner_id.')
    name = fields.Char(string='Description', compute='_compute_name', store=True)

    @api.depends('bsi_reason', 'bsi_referred_partner_id.name', 'bsi_appointment_id.bsi_location_id')
    def _compute_name(self):
        for entry in self:
            if entry.bsi_reason == 'referral':
                entry.name = _('Referral bonus — %s\'s first visit') % (entry.bsi_referred_partner_id.name or _('a friend'))
            else:
                entry.name = _('Booking completed and paid')
