from odoo import models, fields


class BsiSalonValue(models.Model):
    _name = 'bsi.salon.value'
    _description = 'Salon Brand Value'
    _order = 'sequence, id'

    name = fields.Char(string='Title', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_icon = fields.Char(string='Icon', help='A single symbol/glyph, e.g. ◈', default='✦')
    bsi_description = fields.Text(string='Description')
