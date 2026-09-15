from odoo import models, fields, api


class BsiSalonLocation(models.Model):
    _name = 'bsi.salon.location'
    _description = 'Salon Location'
    _order = 'sequence, id'

    name = fields.Char(string='Location Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_city = fields.Char(string='City', required=True, default='Ahmedabad')
    bsi_address = fields.Char(string='Address')
    bsi_phone = fields.Char(string='Phone')
    bsi_email = fields.Char(string='Email')
    bsi_hours_weekdays = fields.Char(string='Hours (Mon-Fri)')
    bsi_hours_saturday = fields.Char(string='Hours (Saturday)')
    bsi_hours_sunday = fields.Char(string='Hours (Sunday)')
    bsi_team_count = fields.Integer(string='Stylist Count')
    bsi_image_url = fields.Char(string='Image URL')
    bsi_image_ids = fields.Many2many('ir.attachment', string='Images')
    bsi_flagship = fields.Boolean(string='Flagship Location')
    bsi_service_ids = fields.Many2many('bsi.salon.service', string='Services Offered')
    bsi_latitude = fields.Float(string='Latitude', digits=(10, 3))
    bsi_longitude = fields.Float(string='Longitude', digits=(10, 3))
    bsi_wait_minutes = fields.Integer(string='Current Wait (minutes)', default=0,
                                       help='0 = walk-ins welcome right now')
    bsi_rating = fields.Float(string='Rating', default=4.8, digits=(2, 1))
    bsi_map_x = fields.Float(string='Map X (%)', default=50.0, help='Position on the stylised city map, 0-100')
    bsi_map_y = fields.Float(string='Map Y (%)', default=50.0, help='Position on the stylised city map, 0-100')
    bsi_booking_ids = fields.One2many(
        'bsi.salon.booking.request', 'bsi_location_id', string='Appointments',
        help='Every appointment ever booked at this branch.')
    bsi_booking_count = fields.Integer(compute='_compute_bsi_booking_count')

    @api.depends('bsi_booking_ids')
    def _compute_bsi_booking_count(self):
        for location in self:
            location.bsi_booking_count = len(location.bsi_booking_ids)
