from odoo import models, fields


class BsiSalonAboutContent(models.Model):
    _name = 'bsi.salon.about.content'
    _description = 'Salon About Us Page Content'

    name = fields.Char(string='Title', default='About Us Content', required=True)
    bsi_hero_eyebrow = fields.Char(string='Hero Eyebrow', default='Our Story')
    bsi_hero_title_line1 = fields.Char(string='Hero Title (line 1)', default='Born from a love')
    bsi_hero_title_line2 = fields.Char(string='Hero Title (line 2, emphasized)', default='of the craft.')
    bsi_story_paragraph_1 = fields.Text(string='Story Paragraph 1')
    bsi_story_paragraph_2 = fields.Text(string='Story Paragraph 2')
    bsi_badge_value = fields.Char(string='Badge Value', default='12+')
    bsi_badge_label = fields.Char(string='Badge Label', default='Years of Excellence')
    bsi_hero_image_url = fields.Char(string='Hero Image URL')
    bsi_image_ids = fields.Many2many('ir.attachment', string='Images')
