from odoo import models, fields, api


class BsiSalonTimeSlot(models.Model):
    _name = 'bsi.salon.time.slot'
    _description = 'Salon Fixed Time Slot'
    _order = 'bsi_start_time, id'

    name = fields.Char(string='Slot Label', required=True, help='e.g. "10:00 AM - 10:45 AM"')
    active = fields.Boolean(string='Active', default=True)
    bsi_start_time = fields.Float(string='Start Time', required=True)
    bsi_end_time = fields.Float(string='End Time', required=True)
    bsi_today_bookings_count = fields.Integer(
        string="Booked Today", compute='_compute_bsi_today_bookings_count',
        help='Non-cancelled bookings using this slot for today\'s date, summed across every branch.')
    bsi_booking_ids = fields.One2many(
        'bsi.salon.booking.request', 'bsi_slot_id', string='Appointments',
        help='Every appointment ever booked into this fixed slot, across every branch and date.')
    bsi_booking_count = fields.Integer(compute='_compute_bsi_booking_count')

    @api.depends('bsi_booking_ids')
    def _compute_bsi_booking_count(self):
        for slot in self:
            slot.bsi_booking_count = len(slot.bsi_booking_ids)

    @api.depends()
    def _compute_bsi_today_bookings_count(self):
        # Depends on live appointment/lead data elsewhere, not on any field of this record
        # itself — always recomputed fresh, never stored.
        today = fields.Date.context_today(self)
        Appointment = self.env['bsi.salon.booking.request'].sudo()
        Lead = self.env['crm.lead'].sudo()
        for slot in self:
            count = (
                Appointment.search_count([
                    ('bsi_slot_id', '=', slot.id), ('bsi_preferred_date', '=', today),
                    ('bsi_state', '!=', 'cancelled'),
                ])
                + Lead.search_count([
                    ('bsi_slot_id', '=', slot.id), ('bsi_preferred_date', '=', today),
                    ('active', '=', True), ('bsi_appointment_id', '=', False),
                ])
            )
            slot.bsi_today_bookings_count = count
