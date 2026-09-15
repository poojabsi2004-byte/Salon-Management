from odoo import models, fields, api, _


class BsiSalonRescheduleWizard(models.TransientModel):
    _name = 'bsi.salon.reschedule.wizard'
    _description = 'Salon Slot Reschedule Wizard'

    lead_id = fields.Many2one('crm.lead', string='Lead', required=True, readonly=True)
    conflict_reason = fields.Char(string='Why', readonly=True)
    customer_name = fields.Char(related='lead_id.contact_name', readonly=True)
    customer_email = fields.Char(related='lead_id.email_from', readonly=True)
    requested_date = fields.Date(related='lead_id.bsi_preferred_date', readonly=True)
    artist_id = fields.Many2one(related='lead_id.bsi_artist_id', string='Artist', readonly=True)
    available_slot_ids = fields.Many2many(
        'bsi.salon.time.slot', string='Available on the Same Day',
        compute='_compute_available_slot_ids',
        help='Other slots on the customer\'s requested date that are free for this same '
             'artist/branch — pick one to mention in the email, or send without one.')
    suggested_slot_id = fields.Many2one(
        'bsi.salon.time.slot', string='Suggest This Slot Instead',
        domain="[('id', 'in', available_slot_ids)]")

    @api.depends('lead_id')
    def _compute_available_slot_ids(self):
        TimeSlot = self.env['bsi.salon.time.slot'].sudo()
        for wizard in self:
            lead = wizard.lead_id
            if not lead or not lead.bsi_preferred_date:
                wizard.available_slot_ids = False
                continue
            candidates = TimeSlot.search([('active', '=', True), ('id', '!=', lead.bsi_slot_id.id)])
            free = self.env['bsi.salon.time.slot']
            for slot in candidates:
                # A lightweight, unsaved "what if this lead used this slot instead" check —
                # same artist/branch/date, just a different slot — reusing the exact same
                # advisory conflict logic rather than a second, separate implementation.
                probe = lead.new({
                    'bsi_use_slot': True,
                    'bsi_slot_id': slot.id,
                    'bsi_preferred_date': lead.bsi_preferred_date,
                    'bsi_location_id': lead.bsi_location_id.id,
                    'bsi_artist_id': lead.bsi_artist_id.id,
                    'active': True,
                })
                if not probe._bsi_get_artist_capacity_conflict_reason():
                    free |= slot
            wizard.available_slot_ids = free

    def action_send_reschedule_email(self):
        self.ensure_one()
        lead = self.lead_id
        template = self.env.ref('bsi_salon_theme.bsi_salon_slot_conflict_mail_template', raise_if_not_found=False)
        if template and lead._bsi_get_contact_email():
            template.sudo().with_context(
                bsi_suggested_slot_name=self.suggested_slot_id.name if self.suggested_slot_id else False,
            ).send_mail(lead.id, force_send=False, email_layout_xmlid='mail.mail_notification_light')
        lead.message_post(body=_(
            'Reschedule email sent to the customer%s.'
        ) % (_(' suggesting the "%s" slot instead') % self.suggested_slot_id.name if self.suggested_slot_id else ''))
        return {'type': 'ir.actions.act_window_close'}
