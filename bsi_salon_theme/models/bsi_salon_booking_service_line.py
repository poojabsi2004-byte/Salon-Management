from odoo import models, fields, api


class BsiSalonBookingServiceLine(models.Model):
    _name = 'bsi.salon.booking.service.line'
    _description = 'Salon Appointment Service Timing'
    _order = 'id'

    bsi_booking_id = fields.Many2one(
        'bsi.salon.booking.request', string='Appointment', required=True, ondelete='cascade')
    bsi_service_id = fields.Many2one(
        'bsi.salon.service', string='Service', required=True, ondelete='restrict')
    # Related so the merged "Services" tab can show one flat list (service details + live
    # execution status) instead of two separate tabs/tables.
    bsi_service_category = fields.Selection(related='bsi_service_id.bsi_category', string='Category')
    bsi_service_duration_label = fields.Char(related='bsi_service_id.bsi_duration', string='Duration Label')
    bsi_service_price = fields.Float(related='bsi_service_id.bsi_price_amount', string='Price')
    bsi_state = fields.Selection(
        [('not_started', 'Not Started'), ('started', 'Started'), ('ended', 'Ended')],
        string='Status', default='not_started', required=True, copy=False)
    bsi_start_time = fields.Datetime(string='Start Time', readonly=True, copy=False)
    bsi_end_time = fields.Datetime(string='End Time', readonly=True, copy=False)
    bsi_duration_minutes = fields.Float(
        string='Duration (min)', compute='_compute_bsi_duration_minutes', store=True,
        help='Minutes actually elapsed between this service\'s Start and End — zero until '
             'both are set.')

    @api.depends('bsi_start_time', 'bsi_end_time')
    def _compute_bsi_duration_minutes(self):
        for line in self:
            if line.bsi_start_time and line.bsi_end_time:
                line.bsi_duration_minutes = round((line.bsi_end_time - line.bsi_start_time).total_seconds() / 60.0, 1)
            else:
                line.bsi_duration_minutes = 0.0

    def action_start_service(self):
        for line in self:
            if line.bsi_state == 'not_started':
                line.write({'bsi_state': 'started', 'bsi_start_time': fields.Datetime.now()})

    def action_end_service(self):
        for line in self:
            if line.bsi_state == 'started':
                line.write({'bsi_state': 'ended', 'bsi_end_time': fields.Datetime.now()})
