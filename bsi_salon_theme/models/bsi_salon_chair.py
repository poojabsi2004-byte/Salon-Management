from odoo import models, fields


class BsiSalonChair(models.Model):
    _name = 'bsi.salon.chair'
    _description = 'Salon Chair / Station'
    _order = 'bsi_location_id, sequence, id'

    name = fields.Char(string='Chair Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_location_id = fields.Many2one(
        'bsi.salon.location', string='Branch', required=True,
        help='Branch this chair belongs to. Appointment chair options are limited to the '
             'branch selected on the appointment.')
    bsi_service_category = fields.Selection(
        [('hair', 'Hair'), ('colour', 'Colour'), ('nails', 'Nails'),
         ('skin', 'Skin'), ('body', 'Body'), ('bridal', 'Bridal')],
        string='Service Type', required=True, default='hair',
        help='Type of service this chair/station is set up for. Appointment chair options '
             'are limited to the categories of the selected services.')
