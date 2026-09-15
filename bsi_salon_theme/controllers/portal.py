from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class BsiSalonCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'bsi_appointment_count' in counters:
            values['bsi_appointment_count'] = request.env['bsi.salon.booking.request'].search_count(
                [('bsi_partner_id', '=', request.env.user.partner_id.id)])
        return values

    @http.route(['/my/appointments', '/my/appointments/page/<int:page>'],
                type='http', auth='user', website=True)
    def bsi_portal_my_appointments(self, page=1, **kwargs):
        Appointment = request.env['bsi.salon.booking.request']
        partner = request.env.user.partner_id
        domain = [('bsi_partner_id', '=', partner.id)]
        appointment_count = Appointment.search_count(domain)
        pager = portal_pager(url='/my/appointments', total=appointment_count, page=page, step=20)
        appointments = Appointment.search(domain, limit=20, offset=pager['offset'], order='create_date desc')
        values = self._prepare_portal_layout_values()
        values.update({
            'appointments': appointments,
            'page_name': 'bsi_appointment',
            'pager': pager,
            'default_url': '/my/appointments',
        })
        return request.render('bsi_salon_theme.bsi_portal_my_appointments', values)

    @http.route(['/my/appointments/<int:appointment_id>'], type='http', auth='user', website=True)
    def bsi_portal_appointment_detail(self, appointment_id, **kwargs):
        appointment = request.env['bsi.salon.booking.request'].browse(appointment_id)
        if not appointment.exists() or appointment.bsi_partner_id != request.env.user.partner_id:
            return request.redirect('/my/appointments')
        values = self._prepare_portal_layout_values()
        values['appointment'] = appointment
        # The review section only ever shows/edits the CURRENT customer's own review, never
        # anyone else's — found by (res_model, res_id, partner_id), the same triple
        # _bsi_submit_review below keys its create-or-update lookup on.
        values['my_review'] = request.env['rating.rating'].sudo().search([
            ('res_model', '=', 'bsi.salon.booking.request'), ('res_id', '=', appointment.id),
            ('partner_id', '=', request.env.user.partner_id.id),
        ], limit=1)
        return request.render('bsi_salon_theme.bsi_portal_appointment_detail', values)

    @http.route(['/my/appointments/<int:appointment_id>/review'],
                type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def bsi_portal_submit_review(self, appointment_id, **post):
        appointment = request.env['bsi.salon.booking.request'].browse(appointment_id)
        # Reviewer is always the logged-in portal user's own account — never taken from the
        # posted form — and only a fully paid/Done visit can be reviewed at all.
        if (appointment.exists() and appointment.bsi_partner_id == request.env.user.partner_id
                and appointment.bsi_state == 'completed'):
            try:
                rating_value = int(post.get('rating') or 0)
            except ValueError:
                rating_value = 0
            try:
                artist_rating_value = int(post.get('artist_rating') or 0)
            except ValueError:
                artist_rating_value = 0
            rating_value = max(1, min(5, rating_value))
            artist_rating_value = max(0, min(5, artist_rating_value)) if appointment.bsi_artist_id else 0
            appointment._bsi_submit_review(rating_value, artist_rating_value, (post.get('feedback') or '').strip())
        return request.redirect('/my/appointments/%d' % appointment_id)
