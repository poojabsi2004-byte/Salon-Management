from odoo import models, fields


class BsiSalonTestimonial(models.Model):
    _name = 'bsi.salon.testimonial'
    _description = 'Salon Client Testimonial'
    _order = 'sequence, id'

    bsi_client_name = fields.Char(string='Client Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    bsi_client_role = fields.Char(string='Client Role', help='e.g. "Regular client since 2021"')
    bsi_text = fields.Text(string='Testimonial Text', required=True)
    bsi_rating = fields.Integer(string='Rating (1-5)', default=5)
    bsi_avatar_url = fields.Char(string='Avatar URL')
    bsi_image_ids = fields.Many2many('ir.attachment', string='Images')
