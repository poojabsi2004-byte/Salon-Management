from odoo import models, fields


class BsiSalonAward(models.Model):
    _name = 'bsi.salon.award'
    _description = 'Salon Award'
    _order = 'bsi_year desc, sequence, id'

    name = fields.Char(string='Award Title', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_year = fields.Char(string='Year', required=True)
