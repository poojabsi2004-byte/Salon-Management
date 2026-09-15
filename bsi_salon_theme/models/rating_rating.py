from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

# The `priority` widget (real clickable stars) only works on a Selection field, and always
# skips its own first option when rendering (see web's PriorityField template) — so a leading
# throwaway "0" entry is required to get exactly 5 stars out of it, for values '1'..'5'.
_BSI_STAR_SELECTION = [('0', 'No Rating'), ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')]


class RatingRating(models.Model):
    _inherit = 'rating.rating'

    # A salon review carries two separate stars: the native `rating` field for the visit
    # overall, and this one for the specific artist who performed the service — kept as a
    # plain custom field rather than routing through `rated_partner_id` (the stock "who is
    # being rated" field), since bsi.salon.team.member has no linked res.partner to point it
    # at (artists aren't contacts/users in this addon).
    bsi_artist_id = fields.Many2one(
        'bsi.salon.team.member', string='Artist',
        help='Artist this review also rates — copied from the appointment when the customer '
             'submits their review.')
    bsi_artist_rating = fields.Float(
        string='Artist Rating', default=0.0,
        help="Customer's separate 1-5 star rating for the artist who performed the service.")

    # Friendly stand-in for the native res_model/res_id pair (a raw ir.model picker + a bare
    # numeric id field — usable, but not something to hand a normal user creating a review
    # from the "Reviews & Ratings" list rather than from an appointment's own "Add Review"
    # button, where res_model_id/res_id are already filled in via context). Only meaningful
    # for salon appointment reviews; stays blank for a rating created by an unrelated app.
    bsi_appointment_id = fields.Many2one(
        'bsi.salon.booking.request', string='Appointment',
        compute='_compute_bsi_appointment_id', inverse='_inverse_bsi_appointment_id')

    @api.depends('res_model', 'res_id')
    def _compute_bsi_appointment_id(self):
        for rec in self:
            rec.bsi_appointment_id = (
                rec.res_id if rec.res_model == 'bsi.salon.booking.request' and rec.res_id else False)

    def _inverse_bsi_appointment_id(self):
        appointment_model = self.env['ir.model']._get('bsi.salon.booking.request')
        for rec in self:
            if rec.bsi_appointment_id:
                rec.res_model_id = appointment_model.id
                rec.res_id = rec.bsi_appointment_id.id

    # Customer is hidden on the form (see bsi_salon_rating_view_form) — showing both fields
    # was redundant, since an appointment only ever has the one customer — so this is what
    # actually fills it in now, instead of the user picking it separately.
    @api.onchange('bsi_appointment_id')
    def _onchange_bsi_appointment_id(self):
        if self.bsi_appointment_id:
            self.partner_id = self.bsi_appointment_id.bsi_partner_id

    # Backend-only star editors: the stock form hides `rating` entirely (it has no widget
    # that can turn a plain Float into clickable stars), so these two Selection fields mirror
    # `rating`/`bsi_artist_rating` just to carry widget="priority" in bsi_salon_rating_view_form
    # — editing a star writes straight back through the inverse, nothing else reads these.
    bsi_rating_stars = fields.Selection(
        _BSI_STAR_SELECTION, string='Overall Rating',
        compute='_compute_bsi_rating_stars', inverse='_inverse_bsi_rating_stars')
    bsi_artist_rating_stars = fields.Selection(
        _BSI_STAR_SELECTION, string='Artist Rating',
        compute='_compute_bsi_artist_rating_stars', inverse='_inverse_bsi_artist_rating_stars')

    @api.depends('rating')
    def _compute_bsi_rating_stars(self):
        for rec in self:
            rec.bsi_rating_stars = str(int(rec.rating)) if rec.rating else '0'

    def _inverse_bsi_rating_stars(self):
        for rec in self:
            rec.rating = int(rec.bsi_rating_stars or '0')

    @api.depends('bsi_artist_rating')
    def _compute_bsi_artist_rating_stars(self):
        for rec in self:
            rec.bsi_artist_rating_stars = str(int(rec.bsi_artist_rating)) if rec.bsi_artist_rating else '0'

    def _inverse_bsi_artist_rating_stars(self):
        for rec in self:
            rec.bsi_artist_rating = int(rec.bsi_artist_rating_stars or '0')

    @api.constrains('bsi_artist_rating')
    def _check_bsi_artist_rating(self):
        for rec in self:
            if not (0 <= rec.bsi_artist_rating <= 5):
                raise ValidationError(_('Artist rating must be between 0 and 5.'))
