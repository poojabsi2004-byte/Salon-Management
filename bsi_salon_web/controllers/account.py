# -*- coding: utf-8 -*-
"""PHASE 6 DEV -- the customer's own history, in the site's own design.

bsi_salon_backend already ships "My Appointments" under Odoo's standard /my
portal (see its controllers/portal.py), and website_sale ships /my/orders. Both
render inside Odoo's default portal chrome, which looks nothing like the Enrich
site a customer arrived from -- clicking an account link dropped them onto a
plain Bootstrap page mid-visit.

These routes answer the same two questions in the site's own language (the same
crimson-on-ink palette, Playfair Display headings and ticket-style cards the
booking flow uses), off the same records. The standard portal pages are left
exactly as they are: staff and anyone deep-linking to /my still get them, and
nothing here re-implements a permission -- every read below is the signed-in
customer's own partner, and a record that is not theirs is redirected away
rather than rendered.
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# Appointment states, as a customer should read them. bsi.salon.booking.request
# splits the visit itself into started/ended, which is one thing from outside.
APPOINTMENT_STATUS = {
    'draft': ('Pending', '#e8a71f'),
    'started': ('In Progress', '#4a9fe8'),
    'ended': ('In Progress', '#4a9fe8'),
    'completed': ('Completed', '#3ddc84'),
    'cancelled': ('Cancelled', '#e8283f'),
}
ORDER_STATUS = {
    'draft': ('Quotation', '#e8a71f'),
    'sent': ('Quotation Sent', '#e8a71f'),
    'sale': ('Confirmed', '#3ddc84'),
    'cancel': ('Cancelled', '#e8283f'),
}
# account.move.payment_state, collapsed the same way the salon dashboard already
# collapses it (see bsi_salon_backend.controllers.dashboard.PAYMENT_STATE_LABELS)
# so the two never disagree about what "paid" means.
PAYMENT_STATUS = {
    'not_paid': ('Unpaid', '#e8283f'),
    'partial': ('Partly Paid', '#e8a71f'),
    'in_payment': ('Paid', '#3ddc84'),
    'paid': ('Paid', '#3ddc84'),
    'reversed': ('Refunded', '#a79a9d'),
    'blocked': ('Unpaid', '#e8283f'),
}
PAGE_SIZE = 12


class BsiSalonAccount(http.Controller):

    # ------------------------------------------------------------------
    # shared
    # ------------------------------------------------------------------

    def _bsi_account_values(self, active):
        partner = request.env.user.partner_id
        return {
            'bsi_active_tab': active,
            'bsi_partner': partner,
            'bsi_user_name': partner.name or request.env.user.name or '',
            'bsi_appointment_status': APPOINTMENT_STATUS,
            'bsi_order_status': ORDER_STATUS,
            'bsi_payment_status': PAYMENT_STATUS,
            'bsi_money': self._bsi_money,
            'bsi_appointment_time': self._bsi_appointment_time,
            'bsi_appointment_services': self._bsi_appointment_services,
            'bsi_order_payment': self._bsi_order_payment,
        }

    # The rupee sign, the same one the rest of the site prints. Every salon figure
    # is authored in rupees (bsi.salon.service.bsi_price is literally the string
    # "\u20b91,299", and the booking flow, packages, memberships and loyalty wallet
    # all render \u20b9 directly), so reading res.company.currency_id here would
    # label those same numbers with whatever currency the Odoo company happens to
    # be set to -- a fresh database defaults to USD, which printed "$599" next to a
    # booking the site had just quoted as "\u20b9599".
    CURRENCY = '\u20b9'

    def _bsi_money(self, amount):
        """One money format for every figure on these pages."""
        return '%s%s' % (self.CURRENCY, '{:,.0f}'.format(round(amount or 0.0)))

    def _bsi_appointment_time(self, appointment):
        """The visit's own time, fixed slot or free-text hour.

        Same two-branch rule sale.order._compute_bsi_appointment_time already
        applies to the same two fields, so an appointment and the order raised
        from it never print different times.
        """
        if appointment.bsi_use_slot and appointment.bsi_slot_id:
            return appointment.bsi_slot_id.name
        if appointment.bsi_preferred_time:
            hours, minutes = divmod(round(appointment.bsi_preferred_time * 60), 60)
            return '%02d:%02d' % (hours, minutes)
        return appointment.bsi_time_slot or ''

    def _bsi_appointment_services(self, appointment):
        """What was booked, as one readable line -- the package if there is one
        (its own services are implied by it), otherwise every service picked."""
        if appointment.bsi_package_id:
            return appointment.bsi_package_id.name
        names = appointment.bsi_service_ids.mapped('name')
        if appointment.bsi_addon_ids:
            names += ['+ %s' % name for name in appointment.bsi_addon_ids.mapped('name')]
        return ', '.join(names)

    def _bsi_order_payment(self, order):
        """(label, colour) for how much of this order has actually been paid.

        Read off the order's own invoices rather than invented here: an order
        with nothing invoiced yet is genuinely "Not Invoiced", not "Unpaid", and
        a partly-invoiced order reports the weakest state of its invoices so a
        half-paid order never reads as paid.
        """
        invoices = order.invoice_ids.filtered(lambda m: m.state != 'cancel')
        if not invoices:
            return ('Not Invoiced', '#a79a9d')
        states = set(invoices.mapped('payment_state'))
        for state in ('not_paid', 'blocked', 'partial', 'in_payment', 'paid', 'reversed'):
            if state in states:
                return PAYMENT_STATUS.get(state, (state, '#a79a9d'))
        return ('Not Invoiced', '#a79a9d')

    def _bsi_pager(self, url, total, page):
        pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, pages))
        return {
            'url': url, 'page': page, 'pages': pages, 'total': total,
            'offset': (page - 1) * PAGE_SIZE,
            'prev': page - 1 if page > 1 else 0,
            'next': page + 1 if page < pages else 0,
            'numbers': list(range(1, pages + 1)) if pages <= 9 else [],
        }

    # ------------------------------------------------------------------
    # bookings / appointments
    # ------------------------------------------------------------------

    @http.route(['/salon/my', '/salon/my/appointments',
                 '/salon/my/appointments/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def bsi_account_appointments(self, page=1, **kwargs):
        partner = request.env.user.partner_id
        # sudo + an explicit partner filter, the same shape Odoo's own portal
        # controllers use: the record rule restricting portal users to their own
        # appointments (see bsi_salon_theme_security.xml) only covers portal
        # users, and an internal user browsing the site should still only see
        # their own history here, not every customer's.
        Appointment = request.env['bsi.salon.booking.request'].sudo()
        domain = [('bsi_partner_id', '=', partner.id)]
        total = Appointment.search_count(domain)
        pager = self._bsi_pager('/salon/my/appointments', total, page)
        appointments = Appointment.search(
            domain, limit=PAGE_SIZE, offset=pager['offset'],
            order='bsi_preferred_date desc, id desc')

        values = self._bsi_account_values('appointments')
        values.update({'appointments': appointments, 'pager': pager})
        return request.render('bsi_salon_web.bsi_account_appointments', values)

    @http.route('/salon/my/appointments/<int:appointment_id>',
                type='http', auth='user', website=True, sitemap=False)
    def bsi_account_appointment_detail(self, appointment_id, **kwargs):
        appointment = request.env['bsi.salon.booking.request'].sudo().browse(appointment_id)
        if not appointment.exists() or appointment.bsi_partner_id != request.env.user.partner_id:
            return request.redirect('/salon/my/appointments')
        values = self._bsi_account_values('appointments')
        values['appointment'] = appointment
        values['my_review'] = request.env['rating.rating'].sudo().search([
            ('res_model', '=', 'bsi.salon.booking.request'), ('res_id', '=', appointment.id),
            ('partner_id', '=', request.env.user.partner_id.id),
        ], limit=1)
        return request.render('bsi_salon_web.bsi_account_appointment_detail', values)

    # ------------------------------------------------------------------
    # orders
    # ------------------------------------------------------------------

    def _bsi_order_domain(self, partner):
        # child_of the commercial partner, matching Odoo's own portal: an order
        # raised against a delivery/invoice contact of the same company still
        # belongs to this customer's history.
        return [('partner_id', 'child_of', partner.commercial_partner_id.id)]

    @http.route(['/salon/my/orders', '/salon/my/orders/page/<int:page>'],
                type='http', auth='user', website=True, sitemap=False)
    def bsi_account_orders(self, page=1, **kwargs):
        partner = request.env.user.partner_id
        Order = request.env['sale.order'].sudo()
        domain = self._bsi_order_domain(partner)
        total = Order.search_count(domain)
        pager = self._bsi_pager('/salon/my/orders', total, page)
        orders = Order.search(domain, limit=PAGE_SIZE, offset=pager['offset'],
                              order='date_order desc, id desc')

        values = self._bsi_account_values('orders')
        values.update({'orders': orders, 'pager': pager})
        return request.render('bsi_salon_web.bsi_account_orders', values)

    @http.route('/salon/my/orders/<int:order_id>',
                type='http', auth='user', website=True, sitemap=False)
    def bsi_account_order_detail(self, order_id, **kwargs):
        order = request.env['sale.order'].sudo().browse(order_id)
        partner = request.env.user.partner_id
        # Re-checked against the same domain the list was built from, rather
        # than a looser "is this my partner" test -- so exactly the orders that
        # appear in the list are the orders that open.
        if not order.exists() or order not in request.env['sale.order'].sudo().search(
                self._bsi_order_domain(partner) + [('id', '=', order.id)]):
            return request.redirect('/salon/my/orders')
        values = self._bsi_account_values('orders')
        values['order'] = order
        return request.render('bsi_salon_web.bsi_account_order_detail', values)
