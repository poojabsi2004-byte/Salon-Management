import os
from datetime import date, datetime, timedelta

from odoo import http, fields
from odoo.http import request
from odoo.modules.module import get_module_path

PAYMENT_STATE_LABELS = {
    'not_paid': 'Pending', 'partial': 'Pending',
    'in_payment': 'Paid', 'paid': 'Paid',
    'reversed': 'Refunded', 'blocked': 'Pending',
}
APPT_STATUS_LABELS = {
    'draft': 'Pending', 'started': 'In Progress',
    'ended': 'In Progress', 'completed': 'Completed', 'cancelled': 'Cancelled',
}


class BsiSalonDashboardController(http.Controller):

    _SIDEBAR_ICONS = {
        'bsi_salon_dashboard_menu': 'dashboard',
        'bsi_salon_booking_request_menu': 'appointments',
        'bsi_salon_ecommerce_product_menu': 'products',
        'bsi_salon_reports_menu': 'reports',
        'bsi_salon_crm_pipeline_menu': 'marketing',
        'bsi_salon_content_menu': 'settings',
    }
    # Sidebar-only display labels — kept separate from the real ir.ui.menu names (which stay
    # unchanged since they're also used as Odoo's own app-menu breadcrumb elsewhere).
    _SIDEBAR_LABELS = {
        'bsi_salon_crm_pipeline_menu': 'Marketing',
        'bsi_salon_content_menu': 'Settings',
        'bsi_salon_ecommerce_product_menu': 'Products',
    }

    def _bsi_dashboard_js_version(self):
        # bsi_salon_dashboard.js is loaded via a plain <script src> (see the template) rather
        # than through Odoo's own asset-bundle system, so it never gets that system's
        # automatic content-hash cache-busting — browsers cache it for a week (see the static
        # file route's Cache-Control) and would otherwise keep serving a stale copy after
        # every edit. A ?v=<mtime> query string forces a fresh fetch whenever the file
        # actually changes, without disturbing anyone's cache the rest of the time.
        try:
            path = os.path.join(get_module_path('bsi_salon_theme'), 'static', 'src', 'js', 'bsi_salon_dashboard.js')
            return int(os.path.getmtime(path))
        except OSError:
            return 0

    def _bsi_resolve_menu_url(self, menu):
        # A pure grouping menu (e.g. "Configuration") has no action of its own — in Odoo's
        # own UI, clicking it just expands its children, but this sidebar has no expandable
        # sub-menus.  Walk through the first child at every heading level until we reach an
        # actionable item, so Settings stays available even when its menus are grouped.
        target = menu
        if not target.action:
            while not target.action:
                child = target.child_id.sorted('sequence')[:1]
                if not child:
                    return False
                target = child
        if target.action._name == 'ir.actions.act_url':
            return target.action.url
        return '/odoo/action-%d' % target.action.id

    @http.route('/salon/dashboard', type='http', auth='user', sitemap=False)
    def bsi_salon_dashboard(self, **kwargs):
        # Rendered inside the "Dashboard" menu's client-action iframe (see
        # static/src/js/bsi_salon_dashboard_client_action.js) — Odoo's own top bar covers
        # global app navigation there, but this sidebar is still shown for quick access
        # without leaving the dashboard's own view; its links open with target="_top" so
        # they navigate the real top-level Odoo shell, not a nested copy inside the iframe.
        Menu = request.env['ir.ui.menu'].sudo()
        root = request.env.ref('bsi_salon_theme.bsi_salon_theme_root_menu')
        items = Menu.search([('parent_id', '=', root.id)], order='sequence')
        settings_action = request.env.ref(
            'bsi_salon_theme.bsi_salon_config_settings_action', raise_if_not_found=False)
        sidebar = []
        for menu in items:
            xmlid = menu.get_external_id().get(menu.id, '')
            key = xmlid.split('.')[-1] if xmlid else ''
            is_dashboard = key == 'bsi_salon_dashboard_menu'
            # Configuration itself is a pure grouping menu (no action of its own — its
            # dropdown in the top bar just lists Booking Setup/Membership/etc.), so the
            # generic "walk to the first actionable child" fallback below would otherwise
            # land the sidebar's gear icon on whatever sorts first under it. Send it to the
            # module's own Settings screen instead — a deliberate destination, not an
            # accident of menu ordering.
            if key == 'bsi_salon_content_menu' and settings_action:
                url = '/odoo/action-%d' % settings_action.id
            else:
                url = False if is_dashboard else self._bsi_resolve_menu_url(menu)
            if not is_dashboard and not url:
                continue
            sidebar.append({
                'name': self._SIDEBAR_LABELS.get(key, menu.name),
                'url': url,
                'icon': self._SIDEBAR_ICONS.get(key, 'circle'),
                'active': is_dashboard,
            })
        user = request.env.user
        appointments_action = request.env.ref('bsi_salon_theme.bsi_salon_booking_request_action', raise_if_not_found=False)
        locations = request.env['bsi.salon.location'].sudo().search([])

        # ── KPI card click-through — one action per card, each with a domain matching
        # exactly the figure computed for it in bsi_salon_dashboard_stats (see
        # views/bsi_salon_dashboard_kpi_actions.xml). ──
        kpi_action_urls = {}
        for kpi_key, xmlid in (
            ('revenue_today', 'bsi_salon_dashboard_kpi_revenue_action'),
            ('appointments_today', 'bsi_salon_dashboard_kpi_appointments_action'),
            ('new_customers', 'bsi_salon_dashboard_kpi_new_customers_action'),
            ('available_staff', 'bsi_salon_dashboard_kpi_available_staff_action'),
            ('pending_payments', 'bsi_salon_dashboard_kpi_pending_payments_action'),
            ('completed_services', 'bsi_salon_dashboard_kpi_completed_services_action'),
        ):
            action = request.env.ref('bsi_salon_theme.%s' % xmlid, raise_if_not_found=False)
            if action:
                kpi_action_urls[kpi_key] = '/odoo/action-%d' % action.id

        # Same Settings toggles that already gate the website sections and backend menus
        # (see models/res_config_settings.py / controllers/main.py's bsi_show()) — reused
        # here so a disabled feature disappears from the dashboard too, not just those.
        ICP = request.env['ir.config_parameter'].sudo()

        def bsi_show(key):
            return ICP.get_param('bsi_salon_theme.show_%s' % key, 'True') == 'True'

        show_membership = bsi_show('membership')
        membership_plan = False
        if show_membership:
            Membership = request.env['bsi.salon.membership'].sudo()
            plan = (Membership.search([('active', '=', True), ('bsi_featured', '=', True)], limit=1)
                    or Membership.search([('active', '=', True)], order='bsi_price_monthly desc', limit=1))
            if plan:
                membership_action = request.env.ref(
                    'bsi_salon_theme.bsi_salon_membership_action', raise_if_not_found=False)
                membership_plan = {
                    'name': plan.name,
                    'tagline': plan.bsi_tagline or '',
                    'price_monthly': plan.bsi_price_monthly,
                    'url': ('/odoo/action-%d' % membership_action.id) if membership_action else False,
                }

        return request.render('bsi_salon_theme.bsi_dashboard_page', {
            'sidebar_items': sidebar,
            'user_name': user.name,
            'user_avatar_url': '/web/image/res.users/%d/avatar_128' % user.id,
            'quick_actions_appointments_url': (
                '/odoo/action-%d' % appointments_action.id) if appointments_action else False,
            'kpi_action_urls': kpi_action_urls,
            'dashboard_today': date.today().isoformat(),
            'locations': [{'id': loc.id, 'name': loc.name} for loc in locations],
            'show_loyalty_points': bsi_show('loyalty_points'),
            'show_referral': bsi_show('referral'),
            'show_gift_card': bsi_show('gift_card'),
            'membership_plan': membership_plan,
            'dashboard_js_version': self._bsi_dashboard_js_version(),
        })

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _bsi_pct_change(self, current, previous):
        if not previous:
            return 100.0 if current else 0.0
        return round((current - previous) / previous * 100.0, 1)

    def _bsi_paid_invoices(self, appointments):
        """Every invoice (linked back to one of these appointments' quotations) with at
        least some payment collected against it — the one source of truth for "real,
        collected salon revenue" used by every money figure on the dashboard (today's
        revenue, trends, top staff, transactions), so they can never silently disagree."""
        invoices = request.env['account.move']
        for appt in appointments:
            invoices |= appt.bsi_sale_order_id.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.payment_state in ('paid', 'in_payment', 'partial') and inv.invoice_date)
        return invoices

    def _bsi_collected_amount(self, invoice):
        # amount_total for a fully/in-payment invoice; for a partially-paid one, only the
        # portion actually collected so far — never the still-outstanding remainder.
        return invoice.amount_total - invoice.amount_residual

    def _bsi_revenue_between(self, invoices, day_from, day_to_exclusive):
        return sum(self._bsi_collected_amount(inv) for inv in invoices
                   if day_from <= inv.invoice_date < day_to_exclusive)

    def _bsi_month_bucket(self, months_ago):
        total_index = date.today().month - 1 - months_ago
        year = date.today().year + total_index // 12
        month = total_index % 12 + 1
        start = date(year, month, 1)
        end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        return start, end

    def _bsi_revenue_series(self, period, location_id=False):
        """Revenue series for the requested period — this module has no vendor-bill/expense
        tracking tied to the salon, so only real, collected revenue is returned (no fabricated
        Expenses/Net Revenue). invoice_date only carries a day of granularity (no time-of-day),
        so 'today' is shown as a single bucket rather than an invented hourly split."""
        Appointment = request.env['bsi.salon.booking.request'].sudo()
        today = date.today()
        domain = [('bsi_sale_order_id', '!=', False)]
        if location_id:
            domain.append(('bsi_location_id', '=', location_id))
        appointments = Appointment.search(domain)
        invoices = self._bsi_paid_invoices(appointments)

        labels, buckets = [], []
        if period == 'today':
            labels.append('Today')
            buckets.append((today, today + timedelta(days=1)))
        elif period == 'week':
            start_day = today - timedelta(days=6)
            for i in range(7):
                day = start_day + timedelta(days=i)
                labels.append(day.strftime('%a'))
                buckets.append((day, day + timedelta(days=1)))
        elif period == 'year':
            for months_ago in range(11, -1, -1):
                start, end = self._bsi_month_bucket(months_ago)
                labels.append(start.strftime('%b'))
                buckets.append((start, end))
        else:  # 'month' (default): each day of the current month so far
            day = today.replace(day=1)
            while day <= today:
                labels.append(day.strftime('%d'))
                buckets.append((day, day + timedelta(days=1)))
                day += timedelta(days=1)

        revenue_series = [round(self._bsi_revenue_between(invoices, start, end), 2) for start, end in buckets]
        return {'labels': labels, 'revenue': revenue_series}

    @http.route('/salon/dashboard/revenue', type='jsonrpc', auth='user')
    def bsi_salon_dashboard_revenue(self, period='month', location_id=None, **kwargs):
        if period not in ('today', 'week', 'month', 'year'):
            period = 'month'
        return self._bsi_revenue_series(period, location_id=int(location_id) if location_id else False)

    def _bsi_notifications(self, pending_invoices):
        """Bounded, real operational alerts — no fabricated categories: appointments left
        unconfirmed too long, invoices left unpaid too long, and recent low ratings."""
        Appointment = request.env['bsi.salon.booking.request'].sudo()
        Rating = request.env['rating.rating'].sudo()
        now = fields.Datetime.now()
        notifications = []

        stale_drafts = Appointment.search([
            ('bsi_state', '=', 'draft'), ('create_date', '<=', now - timedelta(hours=4)),
        ], order='create_date asc', limit=5)
        for appt in stale_drafts:
            notifications.append({
                'type': 'stale_draft',
                'text': '%s has been unconfirmed for over 4 hours' % (
                    appt.bsi_partner_id.name or appt.bsi_name or 'An appointment'),
                'date': appt.create_date.isoformat(),
            })

        old_pending = pending_invoices.filtered(
            lambda inv: inv.invoice_date and inv.invoice_date <= date.today() - timedelta(days=3))[:5]
        for inv in old_pending:
            notifications.append({
                'type': 'unpaid_invoice',
                'text': 'Invoice %s (%s) is still unpaid' % (inv.name, inv.partner_id.name or '—'),
                'date': inv.invoice_date.isoformat(),
            })

        low_ratings = Rating.search([
            ('res_model', '=', 'bsi.salon.booking.request'), ('rating', '>', 0), ('rating', '<', 3),
            ('write_date', '>=', now - timedelta(days=7)),
        ], order='write_date desc', limit=5)
        for r in low_ratings:
            notifications.append({
                'type': 'low_rating',
                'text': 'A recent visit was rated %d/5' % int(r.rating),
                'date': r.write_date.isoformat(),
            })

        notifications.sort(key=lambda n: n['date'], reverse=True)
        return notifications[:10]

    @http.route('/salon/dashboard/stats', type='jsonrpc', auth='user')
    def bsi_salon_dashboard_stats(self, location_id=None, selected_date=None, **kwargs):
        location_id = int(location_id) if location_id else False
        Appointment = request.env['bsi.salon.booking.request'].sudo()
        Partner = request.env['res.partner'].sudo()
        Staff = request.env['bsi.salon.team.member'].sudo()
        Service = request.env['bsi.salon.service'].sudo()
        Rating = request.env['rating.rating'].sudo()

        # `today` below means "the day the dashboard is showing" — defaults to the real
        # today, but every KPI/table on this page reads from it instead of date.today()
        # directly, so picking a different day in the date filter (see bsiDashDate in
        # bsi_salon_dashboard.js) makes the whole page — not just the appointments table —
        # show that day's figures.
        try:
            today = date.fromisoformat(selected_date) if selected_date else date.today()
        except ValueError:
            today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        appt_domain = [('bsi_location_id', '=', location_id)] if location_id else []
        all_appointments = Appointment.search(appt_domain)
        paid_appointments = all_appointments.filtered('bsi_sale_order_id')
        invoices = self._bsi_paid_invoices(paid_appointments)

        # ── KPI: Today's Revenue ─────────────────────────────────────────
        revenue_today = self._bsi_revenue_between(invoices, today, tomorrow)
        revenue_yesterday = self._bsi_revenue_between(invoices, yesterday, today)

        # ── KPI: Today's Appointments ─────────────────────────────────────
        appts_today = all_appointments.filtered(lambda a: a.bsi_preferred_date == today)
        appts_yesterday_count = all_appointments.filtered(
            lambda a: a.bsi_preferred_date == yesterday).__len__()

        # ── KPI: New Customers (first-ever booking created today) ────────
        booked_partner_ids = all_appointments.filtered('bsi_partner_id').mapped('bsi_partner_id.id')
        new_customers_today = Partner.search_count([
            ('id', 'in', booked_partner_ids), ('create_date', '>=', today), ('create_date', '<', tomorrow)])
        new_customers_yesterday = Partner.search_count([
            ('id', 'in', booked_partner_ids), ('create_date', '>=', yesterday), ('create_date', '<', today)])

        # ── KPI: Available Staff (staff tied to another branch are excluded when a
        # branch filter is active; staff with no branch set are available everywhere) ──
        staff_domain = [('active', '=', True)]
        if location_id:
            staff_domain = ['&', ('active', '=', True),
                             '|', ('bsi_location_id', '=', location_id), ('bsi_location_id', '=', False)]
        staff_members = Staff.search(staff_domain)
        total_staff = len(staff_members)
        # Busy FOR THE SELECTED DAY — same rule as bsi.salon.team.member's own
        # _compute_bsi_is_available_now, just keyed off `today` (the picked day) instead of
        # always the real today, so this stays consistent with the rest of the page.
        busy_today = all_appointments.filtered(
            lambda a: a.bsi_preferred_date == today and a.bsi_state not in ('cancelled', 'completed'))
        busy_staff_ids = set(busy_today.mapped('bsi_artist_id.id')) - {False}
        available_staff = max(total_staff - len(busy_staff_ids), 0)

        # ── KPI: Pending Payments (unpaid invoices dated on the selected day) ──────
        pending_invoices = request.env['account.move'].sudo()
        for appt in paid_appointments:
            pending_invoices |= appt.bsi_sale_order_id.invoice_ids.filtered(
                lambda inv: inv.move_type == 'out_invoice'
                and inv.payment_state in ('not_paid', 'partial') and inv.state == 'posted'
                and inv.invoice_date == today)
        pending_amount = sum(inv.amount_residual for inv in pending_invoices)

        # ── KPI: Completed Services (finished today) ──────────────────────
        completed_today = all_appointments.filtered(
            lambda a: a.bsi_state == 'completed' and a.bsi_ended_at and a.bsi_ended_at.date() == today)
        completed_yesterday_count = all_appointments.filtered(
            lambda a: a.bsi_state == 'completed' and a.bsi_ended_at and a.bsi_ended_at.date() == yesterday).__len__()

        # ── Today's appointments list ──────────────────────────────────────
        def bsi_payment_status(appt):
            if not appt.bsi_sale_order_id:
                return 'unbilled'
            invs = appt.bsi_sale_order_id.invoice_ids
            if not invs:
                return 'unbilled'
            if any(inv.payment_state in ('paid', 'in_payment') for inv in invs):
                return 'paid'
            return 'pending'

        # LIFO — the most recently booked appointment shows first, not the earliest time
        # slot, so staff immediately notice a brand new booking without scrolling.
        appts_today_sorted = appts_today.sorted(key=lambda a: a.create_date, reverse=True)
        appointments_today_data = [{
            'id': appt.id,
            'time': appt.bsi_slot_id.name if appt.bsi_use_slot and appt.bsi_slot_id else (
                '%02d:%02d' % divmod(round((appt.bsi_preferred_time or 0) * 60), 60)),
            'customer': appt.bsi_partner_id.name or appt.bsi_name or 'Guest',
            'avatar_url': ('/web/image/res.partner/%d/avatar_128' % appt.bsi_partner_id.id)
                if appt.bsi_partner_id else False,
            'service': (appt.bsi_package_id.name if appt.bsi_package_id
                        else ', '.join(appt.bsi_service_ids.mapped('name')) or '—'),
            'staff': appt.bsi_artist_id.name or 'Unassigned',
            'duration': (appt.bsi_service_ids[:1].bsi_duration if appt.bsi_service_ids else False) or '—',
            'status': appt.bsi_state,
            'status_label': APPT_STATUS_LABELS.get(appt.bsi_state, appt.bsi_state),
            'payment_status': bsi_payment_status(appt),
        } for appt in appts_today_sorted]

        # ── Appointment status donut (real states — 4 buckets shown to match
        # Completed / Pending / In Progress / Cancelled) ──────────
        by_state_raw = {s: all_appointments.filtered(lambda a, s=s: a.bsi_state == s).__len__()
                        for s in ('draft', 'started', 'ended', 'completed', 'cancelled')}
        appointment_stats = {
            'completed': by_state_raw['completed'],
            'pending': by_state_raw['draft'],
            'in_progress': by_state_raw['started'] + by_state_raw['ended'],
            'cancelled': by_state_raw['cancelled'],
        }

        # ── Popular services ────────────────────────────────────────────
        popular = []
        for service in Service.search([('active', '=', True)]):
            bookings = all_appointments.filtered(
                lambda a, s=service: s in a.bsi_service_ids and a.bsi_state != 'cancelled').__len__()
            if bookings:
                popular.append({
                    'id': service.id,
                    'name': service.name,
                    'bookings': bookings,
                    'revenue': round(bookings * service._bsi_get_effective_price(), 2),
                })
        popular.sort(key=lambda p: p['bookings'], reverse=True)
        popular = popular[:30]  # generous cap — the dashboard paginates through these client-side
        max_bookings = max([p['bookings'] for p in popular], default=1)
        for p in popular:
            p['pct'] = round(p['bookings'] / max_bookings * 100)

        # ── Top staff ────────────────────────────────────────────────────
        top_staff = []
        for member in staff_members:
            member_appts = all_appointments.filtered(lambda a, m=member: a.bsi_artist_id == m)
            completed = member_appts.filtered(lambda a: a.bsi_state == 'completed')
            if not completed:
                continue
            member_revenue = sum(
                self._bsi_collected_amount(inv)
                for appt in completed.filtered('bsi_sale_order_id')
                for inv in appt.bsi_sale_order_id.invoice_ids
                if inv.move_type == 'out_invoice'
                and inv.payment_state in ('paid', 'in_payment', 'partial') and inv.invoice_date)
            ratings = Rating.search([
                ('res_model', '=', 'bsi.salon.booking.request'),
                ('res_id', 'in', member_appts.ids), ('rating', '>', 0)])
            avg_rating = (sum(ratings.mapped('rating')) / len(ratings)) if ratings else 0.0
            top_staff.append({
                'id': member.id,
                'name': member.name,
                'role': member.bsi_role or '',
                'avatar_url': member.bsi_image_url or ('/web/image/bsi.salon.team.member/%d/bsi_image' % member.id),
                'services_completed': len(completed),
                'revenue': round(member_revenue, 2),
                'rating': round(avg_rating, 1),
                'is_available': member.bsi_is_available_now,
            })
        top_staff.sort(key=lambda s: s['revenue'], reverse=True)
        top_staff = top_staff[:30]  # generous cap — paginated client-side
        # Performance bar is relative to whoever ranks #1 by revenue — the same metric the
        # list is sorted by — rather than a fabricated absolute score against a fixed ceiling.
        top_revenue = top_staff[0]['revenue'] if top_staff else 0
        for s in top_staff:
            s['performance_pct'] = round(s['revenue'] / top_revenue * 100) if top_revenue else 0

        # ── Recent transactions (paid-invoice trail, newest first) ────────
        def bsi_payment_method(invoice):
            payment = invoice._get_reconciled_payments()[:1]
            if not payment:
                return '—'
            return payment.payment_method_line_id.name or payment.journal_id.name or '—'

        recent_invoices = invoices.sorted(key=lambda inv: inv.invoice_date or date.min, reverse=True)[:30]
        transactions = [{
            'ref': inv.name,
            'customer': inv.partner_id.name or '—',
            'amount': inv.amount_total,
            'method': bsi_payment_method(inv),
            'date': inv.invoice_date.isoformat() if inv.invoice_date else '',
            'status': PAYMENT_STATE_LABELS.get(inv.payment_state, 'Pending'),
        } for inv in recent_invoices]

        # ── Upcoming appointments (next few not-yet-done, today or later — distinct from
        # the Today's Appointments table, which only covers today) ────────────────────
        def bsi_time_label(appt):
            if appt.bsi_use_slot and appt.bsi_slot_id:
                return appt.bsi_slot_id.name
            return '%02d:%02d' % divmod(round((appt.bsi_preferred_time or 0) * 60), 60)

        upcoming = all_appointments.filtered(
            lambda a: a.bsi_state == 'draft'
            and a.bsi_preferred_date and a.bsi_preferred_date >= today
        ).sorted(key=lambda a: (a.bsi_preferred_date, a.bsi_preferred_time or 0))[:30]
        upcoming_data = [{
            'id': appt.id,
            'customer': appt.bsi_partner_id.name or appt.bsi_name or 'Guest',
            'service': (appt.bsi_package_id.name if appt.bsi_package_id
                        else ', '.join(appt.bsi_service_ids.mapped('name')) or '—'),
            'staff': appt.bsi_artist_id.name or 'Unassigned',
            'date': appt.bsi_preferred_date.isoformat(),
            'time': bsi_time_label(appt),
            'status': appt.bsi_state,
            'status_label': APPT_STATUS_LABELS.get(appt.bsi_state, appt.bsi_state),
        } for appt in upcoming]

        # ── Recent leads (not yet converted to a booking — this is the "what's arriving"
        # view; a lead disappears from here the moment it's Won and successfully becomes an
        # appointment, at which point it's already visible in Today's/Upcoming Bookings
        # instead. A Won lead that's still here has no bsi_appointment_id despite being Won —
        # that only happens when a slot/artist conflict blocked the automatic conversion (see
        # crm_lead.py's _bsi_create_appointment_from_lead), so it's flagged for a staff retry
        # rather than shown as if it were still a fresh, unactioned lead.) ──────────────
        Lead = request.env['crm.lead'].sudo()
        lead_domain = [('type', '=', 'opportunity'), ('active', '=', True), ('bsi_appointment_id', '=', False)]
        if location_id:
            lead_domain.append(('bsi_location_id', '=', location_id))
        recent_leads = Lead.search(lead_domain, order='create_date desc', limit=30)
        recent_leads_data = [{
            'id': lead.id,
            'customer': lead.contact_name or lead.partner_id.name or lead.name or 'Unknown',
            'service': (lead.bsi_package_id.name if lead.bsi_package_id
                        else ', '.join(lead.bsi_service_ids.mapped('name')) or '—'),
            'location': lead.bsi_location_id.name or '—',
            'stage': lead.stage_id.name or '—',
            'is_won_pending': bool(lead.stage_id.is_won),
            'date': lead.create_date.isoformat() if lead.create_date else '',
        } for lead in recent_leads]

        # ── Loyalty & referrals (global, not location-scoped — res.partner carries no
        # branch field, same as new_customers above). Computed unconditionally; whether
        # the cards actually show is decided server-side in the GET route via the
        # Settings toggles (show_loyalty_points/show_referral) that gate the template. ──
        Point = request.env['bsi.salon.loyalty.point'].sudo()
        all_points = Point.search([])
        top_earners = Partner.search([('bsi_loyalty_points', '>', 0)], order='bsi_loyalty_points desc', limit=5)
        loyalty = {
            'total_points': sum(all_points.mapped('bsi_points')),
            'top_earners': [{'id': p.id, 'name': p.name, 'points': p.bsi_loyalty_points} for p in top_earners],
        }

        referral_entries = all_points.filtered(lambda p: p.bsi_reason == 'referral')
        referrer_points = {}
        for entry in referral_entries:
            referrer_points.setdefault(entry.bsi_partner_id, 0)
            referrer_points[entry.bsi_partner_id] += entry.bsi_points
        top_referrer = max(referrer_points.items(), key=lambda kv: kv[1]) if referrer_points else None
        referral = {
            'bonus_count': len(referral_entries),
            'bonus_points': sum(referral_entries.mapped('bsi_points')),
            'top_referrer': {'id': top_referrer[0].id, 'name': top_referrer[0].name, 'points': top_referrer[1]} if top_referrer else None,
        }

        # ── Quick action links (deep-link to a blank record form for that action) ──
        def bsi_new_record_url(xmlid):
            action = request.env.ref(xmlid, raise_if_not_found=False)
            return ('/odoo/action-%d/new' % action.id) if action else False

        quick_actions = {
            'new_appointment': bsi_new_record_url('bsi_salon_theme.bsi_salon_booking_request_action'),
            'new_customer': bsi_new_record_url('base.action_partner_form'),
            'new_sale': bsi_new_record_url('sale.action_orders'),
            'add_service': bsi_new_record_url('bsi_salon_theme.bsi_salon_service_action'),
            'add_staff': bsi_new_record_url('bsi_salon_theme.bsi_salon_team_member_action'),
            'create_invoice': bsi_new_record_url('account.action_move_out_invoice_type'),
        }

        notifications = self._bsi_notifications(pending_invoices)

        return {
            'kpis': {
                'revenue_today': {
                    'value': round(revenue_today, 2), 'is_money': True,
                    'change_pct': self._bsi_pct_change(revenue_today, revenue_yesterday)},
                'appointments_today': {
                    'value': len(appts_today), 'is_money': False,
                    'change_pct': self._bsi_pct_change(len(appts_today), appts_yesterday_count)},
                'new_customers': {
                    'value': new_customers_today, 'is_money': False,
                    'change_pct': self._bsi_pct_change(new_customers_today, new_customers_yesterday)},
                'available_staff': {'value': available_staff, 'total': total_staff, 'is_money': False},
                'pending_payments': {'value': round(pending_amount, 2), 'is_money': True},
                'completed_services': {
                    'value': len(completed_today), 'is_money': False,
                    'change_pct': self._bsi_pct_change(len(completed_today), completed_yesterday_count)},
            },
            'appointments_today': appointments_today_data,
            'appointment_stats': appointment_stats,
            'popular_services': popular,
            'top_staff': top_staff,
            'upcoming_appointments': upcoming_data,
            'recent_leads': recent_leads_data,
            'transactions': transactions,
            'loyalty': loyalty,
            'referral': referral,
            'quick_actions': quick_actions,
            'notifications': notifications,
            'notification_count': len(notifications),
            'location_id': location_id,
            'selected_date': today.isoformat(),
            'is_today': today == date.today(),
            'generated_at': fields.Datetime.now().isoformat(),
        }
