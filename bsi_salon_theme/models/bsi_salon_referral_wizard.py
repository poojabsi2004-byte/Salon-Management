from urllib.parse import quote

from odoo import models, fields, api, _


class BsiSalonReferralWizard(models.TransientModel):
    _name = 'bsi.salon.referral.wizard'
    _description = 'Share My Referral Code'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    bsi_loyalty_points = fields.Integer(related='partner_id.bsi_loyalty_points', string='Loyalty Points')
    bsi_referral_code = fields.Char(string='Referral Code', readonly=True)
    bsi_referral_link = fields.Char(string='Referral Link', readonly=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        partner = self.env.user.partner_id
        code = partner._bsi_get_or_create_referral_code()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        vals.update({
            'partner_id': partner.id,
            'bsi_referral_code': code,
            'bsi_referral_link': '%s/salon/booking?ref=%s' % (base_url, code),
        })
        return vals

    def action_share_whatsapp(self):
        self.ensure_one()
        message = _(
            "Hey! I use Enrich for my salon appointments and thought you'd like it too. Book "
            "your first visit with my referral code %(code)s (or just tap: %(link)s) and once "
            "your appointment's done and paid, we both earn loyalty points!"
        ) % {'code': self.bsi_referral_code, 'link': self.bsi_referral_link}
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://wa.me/?text=%s' % quote(message),
            'target': 'new',
        }
