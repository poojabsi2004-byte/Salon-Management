import re

from odoo import models, fields, api


class BsiSalonPackage(models.Model):
    _name = 'bsi.salon.package'
    _description = 'Salon Bundle Package'
    _order = 'sequence, id'

    name = fields.Char(string='Package Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_description = fields.Text(string='Description')
    bsi_includes = fields.Text(string='Includes', help='One included item per line — display '
                                                         'text only; use Included Services below '
                                                         'for the real, bookable services.')
    bsi_service_ids = fields.Many2many(
        'bsi.salon.service', string='Included Services',
        help='The real services this package bundles — auto-filled onto an appointment/lead '
             'when this package is chosen there, replacing an individual service pick.')
    bsi_original_price = fields.Char(string='Original Price Label')
    bsi_bundle_price = fields.Char(string='Bundle Price Label')
    bsi_bundle_price_amount = fields.Float(
        string='Bundle Price Amount',
        help='Numeric price (company currency) used to price a quotation built from this '
             'package — falls back to parsing Bundle Price Label if left blank.')
    bsi_save_label = fields.Char(string='Savings Label', help='e.g. "Save £45"')
    bsi_image_url = fields.Char(string='Image URL')
    bsi_image_ids = fields.Many2many('ir.attachment', string='Images')
    bsi_booking_ids = fields.One2many(
        'bsi.salon.booking.request', 'bsi_package_id', string='Appointments',
        help='Every appointment booked with this package.')
    bsi_booking_count = fields.Integer(compute='_compute_bsi_booking_count')

    @api.depends('bsi_booking_ids')
    def _compute_bsi_booking_count(self):
        for package in self:
            package.bsi_booking_count = len(package.bsi_booking_ids)

    def _bsi_parse_bundle_price_label(self):
        self.ensure_one()
        if not self.bsi_bundle_price:
            return 0.0
        match = re.search(r'[\d,]+(?:\.\d+)?', self.bsi_bundle_price)
        if not match:
            return 0.0
        try:
            return float(match.group(0).replace(',', ''))
        except ValueError:
            return 0.0

    def _bsi_get_effective_price(self):
        self.ensure_one()
        return self.bsi_bundle_price_amount or self._bsi_parse_bundle_price_label()
