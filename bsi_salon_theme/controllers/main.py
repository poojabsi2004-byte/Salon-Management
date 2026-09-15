from datetime import date
from urllib.parse import quote

from odoo import http
from odoo.exceptions import ValidationError
from odoo.http import request


class BsiSalonThemeController(http.Controller):

    _BSI_SHOP_PAGE_SIZE = 12
    _BSI_SHOP_SORT_OPTIONS = {
        'name': 'name asc',
        'price_asc': 'list_price asc',
        'price_desc': 'list_price desc',
        'newest': 'id desc',
    }

    @http.route('/salon/shop', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_shop(self, category=None, search='', sort='name', page=1, **kwargs):
        Product = request.env['product.template']
        domain = [('website_published', '=', True), ('sale_ok', '=', True)]

        category_id = int(category) if category and str(category).isdigit() else False
        if category_id:
            domain.append(('public_categ_ids', 'child_of', category_id))

        search = (search or '').strip()
        if search:
            domain.append(('name', 'ilike', search))

        sort = sort if sort in self._BSI_SHOP_SORT_OPTIONS else 'name'
        try:
            page = max(int(page), 1)
        except (TypeError, ValueError):
            page = 1

        total = Product.search_count(domain)
        pages = max(1, -(-total // self._BSI_SHOP_PAGE_SIZE))
        page = min(page, pages)
        products = Product.search(
            domain, order=self._BSI_SHOP_SORT_OPTIONS[sort],
            limit=self._BSI_SHOP_PAGE_SIZE, offset=(page - 1) * self._BSI_SHOP_PAGE_SIZE)

        values = {
            'active_page': 'shop',
            'products': products,
            'categories': request.env['product.public.category'].sudo().search([('parent_id', '=', False)]),
            'selected_category': category_id,
            'search': search,
            'sort': sort,
            'page': page,
            'pages': pages,
            'total': total,
        }
        return request.render('bsi_salon_theme.bsi_page_shop', values)

    @http.route('/salon', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_home(self, **kwargs):
        Service = request.env['bsi.salon.service'].sudo()
        Testimonial = request.env['bsi.salon.testimonial'].sudo()
        Location = request.env['bsi.salon.location'].sudo()
        featured = Service.browse()
        for category in ('hair', 'skin', 'nails'):
            featured |= Service.search(
                [('bsi_category', '=', category), ('bsi_popular', '=', True)], limit=1)
        values = {
            'active_page': 'home',
            'featured_services': featured,
            'testimonials': Testimonial.search([]),
            'location_count': Location.search_count([]),
        }
        return request.render('bsi_salon_theme.bsi_page_home', values)

    @http.route('/salon/about', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_about(self, **kwargs):
        values = {
            'active_page': 'about',
            'about_content': request.env['bsi.salon.about.content'].sudo().search([], limit=1),
            'values': request.env['bsi.salon.value'].sudo().search([]),
            'team_members': request.env['bsi.salon.team.member'].sudo().search([]),
            'awards': request.env['bsi.salon.award'].sudo().search([]),
        }
        return request.render('bsi_salon_theme.bsi_page_about', values)

    @http.route('/salon/offers', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_offers(self, **kwargs):
        values = {
            'active_page': 'offers',
            'services': request.env['bsi.salon.service'].sudo().search([]),
        }
        return request.render('bsi_salon_theme.bsi_page_offers', values)

    @http.route('/salon/packages', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_packages(self, **kwargs):
        ICP = request.env['ir.config_parameter'].sudo()

        def bsi_show(key):
            return ICP.get_param('bsi_salon_theme.show_%s' % key, 'True') == 'True'

        values = {
            'active_page': 'packages',
            'memberships': request.env['bsi.salon.membership'].sudo().search([]),
            'packages': request.env['bsi.salon.package'].sudo().search([]),
            'show_membership': bsi_show('membership'),
            'show_packages': bsi_show('packages'),
            'show_loyalty_points': bsi_show('loyalty_points'),
            'show_referral': bsi_show('referral'),
            'show_gift_card': bsi_show('gift_card'),
        }
        return request.render('bsi_salon_theme.bsi_page_packages', values)

    @http.route('/salon/membership/product', type='jsonrpc', auth='public', website=True)
    def bsi_salon_membership_product(self, membership_id=None, billing_period='monthly', **kwargs):
        """Resolve (lazily creating if needed) the sellable product for a membership tier +
        billing period, so the "Choose <tier>" CTA can add it to the customer's cart via the
        stock /shop/cart/add endpoint — no custom cart/payment code, just product resolution."""
        membership = request.env['bsi.salon.membership'].sudo().browse(int(membership_id or 0))
        if not membership.exists() or billing_period not in ('monthly', 'yearly'):
            return {'error': True}
        product = membership._bsi_get_or_create_product(billing_period)
        return {'product_id': product.id, 'product_template_id': product.product_tmpl_id.id}

    @http.route('/salon/booking/membership_status', type='jsonrpc', auth='public', website=True)
    def bsi_salon_booking_membership_status(self, email=None, phone=None, **kwargs):
        """Best-effort preview of whether an email/phone already has an active membership, so
        the booking wizard can show the customer their real tier/discount before they submit —
        the server-side compute on the appointment is the actual authority either way."""
        email = (email or '').strip()
        phone = (phone or '').strip()
        if not email and not phone:
            return {'is_member': False}
        contact_domain = [('bsi_partner_id.email', '=', email)] if email else [('bsi_partner_id.phone', '=', phone)]
        subs = request.env['bsi.salon.membership.subscription'].sudo().search(contact_domain + [
            ('bsi_state', '=', 'active'), ('bsi_end_date', '>=', date.today().isoformat()),
        ])
        if not subs:
            return {'is_member': False}
        membership = max(subs.mapped('bsi_membership_id'), key=lambda m: m.bsi_discount_percent)
        return {
            'is_member': True,
            'name': membership.name,
            'discount_percent': membership.bsi_discount_percent,
        }

    @http.route('/salon/our-salons', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_stores(self, **kwargs):
        locations = request.env['bsi.salon.location'].sudo().search([])
        cities = sorted(set(locations.mapped('bsi_city')))
        selected_city = kwargs.get('city') or (cities[0] if cities else False)
        city_locations = locations.filtered(lambda l: l.bsi_city == selected_city) if selected_city else locations
        values = {
            'active_page': 'stores',
            'cities': cities,
            'selected_city': selected_city,
            'locations': city_locations,
            'all_locations': locations,
            'selected_location': city_locations[0] if city_locations else None,
        }
        return request.render('bsi_salon_theme.bsi_page_stores', values)

    @http.route('/salon/stylists', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_stylists(self, **kwargs):
        values = {
            'active_page': 'stylists',
            'team_members': request.env['bsi.salon.team.member'].sudo().search([]),
        }
        return request.render('bsi_salon_theme.bsi_page_stylists', values)

    @http.route('/salon/booking', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_booking(self, **kwargs):
        locations = request.env['bsi.salon.location'].sudo().search([])
        cities = sorted(set(locations.mapped('bsi_city')))
        city_counts = {}
        for loc in locations:
            city_counts[loc.bsi_city] = city_counts.get(loc.bsi_city, 0) + 1
        values = {
            'active_page': 'booking',
            'cities': cities,
            'city_counts': city_counts,
            'locations': locations,
            'services': request.env['bsi.salon.service'].sudo().search([]),
            'chairs': request.env['bsi.salon.chair'].sudo().search([]),
            'artists': request.env['bsi.salon.team.member'].sudo().search([]),
            'time_slots': request.env['bsi.salon.time.slot'].sudo().search([]),
            'today': date.today().isoformat(),
            'error': kwargs.get('error'),
            'referral_code': kwargs.get('ref'),
        }
        return request.render('bsi_salon_theme.bsi_page_booking', values)

    @http.route('/salon/booking/slot_availability', type='jsonrpc', auth='public', website=True)
    def bsi_salon_booking_slot_availability(self, location_id=None, preferred_date=None, artist_id=None,
                                             chair_ids=None, **kwargs):
        """Remaining capacity per time slot for a branch/date, so the wizard can grey out
        slots that are already full before the customer picks one. Mirrors the checks in
        bsi.salon.booking.mixin._bsi_check_slot_capacity_common (the actual guard — this is
        just a preview): a selected chair or a selected artist only conflicts with itself;
        "no preference" bookings have no flat cap to share, so they're always available.
        Counts both confirmed appointments AND leads still pending a Won decision — a
        booking claims its slot the moment it's submitted, not only once staff act on it, so
        the preview a customer sees stays accurate even for slots others currently have a
        pending request on."""
        location_id = int(location_id) if str(location_id or '').isdigit() else False
        artist_id = int(artist_id) if str(artist_id or '').isdigit() else False
        chair_id_list = [int(c) for c in (chair_ids or '').split(',') if c.isdigit()]
        if not location_id or not preferred_date:
            return {}
        Booking = request.env['bsi.salon.booking.request'].sudo()
        Lead = request.env['crm.lead'].sudo()
        availability = {}
        for slot in request.env['bsi.salon.time.slot'].sudo().search([]):
            appt_domain = [
                ('bsi_slot_id', '=', slot.id),
                ('bsi_preferred_date', '=', preferred_date),
                ('bsi_location_id', '=', location_id),
                ('bsi_state', '!=', 'cancelled'),
            ]
            lead_domain = [
                ('bsi_slot_id', '=', slot.id),
                ('bsi_preferred_date', '=', preferred_date),
                ('bsi_location_id', '=', location_id),
                ('active', '=', True),
                ('bsi_appointment_id', '=', False),
            ]
            if chair_id_list and (
                Booking.search_count(appt_domain + [('bsi_chair_ids', 'in', chair_id_list)])
                or Lead.search_count(lead_domain + [('bsi_chair_ids', 'in', chair_id_list)])
            ):
                availability[slot.id] = 0
            elif artist_id:
                taken = (
                    Booking.search_count(appt_domain + [('bsi_artist_id', '=', artist_id)])
                    or Lead.search_count(lead_domain + [('bsi_artist_id', '=', artist_id)])
                )
                availability[slot.id] = 0 if taken else 1
            else:
                # No flat per-slot cap anymore — a "no preference" booking is always
                # available; only a specific chair or artist can actually be full.
                availability[slot.id] = 1
        return availability

    @http.route('/salon/booking/resource_availability', type='jsonrpc', auth='public', website=True)
    def bsi_salon_booking_resource_availability(self, location_id=None, preferred_date=None, slot_id=None, **kwargs):
        """For a specific branch/date/slot, which chairs and which artists are already
        taken — the same conflict rules as slot_availability above, just broken out per
        resource instead of collapsed into one remaining-capacity number. The chair and
        artist steps come BEFORE the date/slot step in this wizard, so there's usually no
        date yet the first time through (returns empty in that case) — this only produces
        a real signal once a date+slot are already chosen, e.g. when the customer navigates
        back to change their chair/artist pick after already reaching the date/slot step."""
        location_id = int(location_id) if str(location_id or '').isdigit() else False
        slot_id = int(slot_id) if str(slot_id or '').isdigit() else False
        if not (location_id and preferred_date and slot_id):
            return {'chairs': {}, 'artists': {}}

        Booking = request.env['bsi.salon.booking.request'].sudo()
        Lead = request.env['crm.lead'].sudo()
        appt_domain = [
            ('bsi_slot_id', '=', slot_id),
            ('bsi_preferred_date', '=', preferred_date),
            ('bsi_location_id', '=', location_id),
            ('bsi_state', '!=', 'cancelled'),
        ]
        lead_domain = [
            ('bsi_slot_id', '=', slot_id),
            ('bsi_preferred_date', '=', preferred_date),
            ('bsi_location_id', '=', location_id),
            ('active', '=', True),
            ('bsi_appointment_id', '=', False),
        ]
        busy_chair_ids = set(
            Booking.search(appt_domain).mapped('bsi_chair_ids.id')
            + Lead.search(lead_domain).mapped('bsi_chair_ids.id')
        )
        busy_artist_ids = set(
            Booking.search(appt_domain + [('bsi_artist_id', '!=', False)]).mapped('bsi_artist_id.id')
            + Lead.search(lead_domain + [('bsi_artist_id', '!=', False)]).mapped('bsi_artist_id.id')
        )
        chairs = request.env['bsi.salon.chair'].sudo().search([('bsi_location_id', '=', location_id)])
        artists = request.env['bsi.salon.team.member'].sudo().search(
            ['|', ('bsi_location_id', '=', location_id), ('bsi_location_id', '=', False)])
        return {
            'chairs': {c.id: (c.id not in busy_chair_ids) for c in chairs},
            'artists': {a.id: (a.id not in busy_artist_ids) for a in artists},
        }

    @http.route('/salon/booking/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def bsi_salon_booking_submit(self, **post):
        location = request.env['bsi.salon.location'].sudo().browse(int(post.get('location_id') or 0))
        service_ids = [int(v) for v in (post.get('service_ids') or '').split(',') if v.isdigit()]
        chair_ids = [int(v) for v in (post.get('chair_ids') or '').split(',') if v.isdigit()]
        use_slot = post.get('use_slot') == '1'
        name = post.get('name')

        # A website booking only ever creates a CRM lead (Draft/New) — the appointment
        # itself is only ever created once a member of staff marks this lead Won (see
        # crm.lead._bsi_create_appointment_from_lead). Slot/chair/artist capacity is still
        # enforced here, on the lead, via the shared bsi.salon.booking.mixin constraint, so
        # the protection against double-booking is exactly as strict as before — it just
        # moved from the (now not-yet-existing) appointment to the lead.
        vals = {
            'name': 'Salon Appointment - %s' % (name or post.get('email') or post.get('phone') or 'Website'),
            'type': 'opportunity',
            'contact_name': name,
            'email_from': post.get('email'),
            'phone': post.get('phone'),
            'partner_id': request.env.user.partner_id.id if request.env.user.has_group('base.group_portal') else False,
            'bsi_city': location.bsi_city if location else False,
            'bsi_location_id': location.id if location else False,
            'bsi_service_ids': [(6, 0, service_ids)],
            'bsi_chair_ids': [(6, 0, chair_ids)],
            'bsi_artist_id': int(post['artist_id']) if (post.get('artist_id') or '').isdigit() else False,
            'bsi_preferred_date': post.get('preferred_date') or False,
            'bsi_use_slot': use_slot,
            'bsi_is_member': bool(post.get('is_member')),
            'bsi_notes': post.get('notes'),
            'bsi_referral_code_used': (post.get('referral_code') or '').strip().upper() or False,
        }
        if use_slot:
            vals['bsi_slot_id'] = int(post['slot_id']) if (post.get('slot_id') or '').isdigit() else False
        else:
            hours, _, minutes = (post.get('preferred_time') or '').partition(':')
            if hours.isdigit():
                vals['bsi_preferred_time'] = int(hours) + (int(minutes) / 60.0 if minutes.isdigit() else 0.0)

        try:
            request.env['crm.lead'].sudo().create(vals)
        except ValidationError as exc:
            # @api.constrains (e.g. the shared slot-capacity check) only raises AFTER the row
            # is already written within this request's open transaction — since that
            # exception is caught here rather than left to propagate to Odoo's request
            # dispatcher, the transaction is never auto-rolled-back, so the "rejected" lead
            # would otherwise still get committed once this request finishes normally. Roll
            # back explicitly so a failed booking never actually gets persisted.
            request.env.cr.rollback()
            return request.redirect('/salon/booking?error=%s&location_id=%s' % (
                quote(exc.args[0]), location.id if location else ''))

        first_name = (name or '').split(' ')[0]
        return request.redirect('/salon/booking?submitted=1&name=%s' % first_name)

    @http.route('/salon/contact', type='http', auth='public', website=True, sitemap=True)
    def bsi_salon_contact(self, submitted=None, name=None, **kwargs):
        values = {
            'active_page': 'contact',
            'locations': request.env['bsi.salon.location'].sudo().search([]),
            'submitted': submitted,
            'submitted_name': name,
        }
        return request.render('bsi_salon_theme.bsi_page_contact', values)

    @http.route('/salon/contact/submit', type='http', auth='public', website=True, methods=['POST'], csrf=True)
    def bsi_salon_contact_submit(self, **post):
        location = request.env['bsi.salon.location'].sudo().search(
            [('name', '=', post.get('location'))], limit=1)
        name = post.get('name')
        # Same CRM-first flow as the booking wizard: this only ever creates a lead — no
        # appointment exists until a staff member marks it Won. The "service" field here is
        # a free-text interest, not an actual service selection (no chair/slot/artist is
        # captured on this simpler form), so it's folded into the notes rather than needing
        # its own field on the lead.
        notes = '\n'.join(filter(None, [
            ('Interested in: %s' % post.get('service')) if post.get('service') else None,
            post.get('notes'),
        ])) or False
        request.env['crm.lead'].sudo().create({
            'name': 'Salon Contact - %s' % (name or post.get('email') or post.get('phone') or 'Website'),
            'type': 'opportunity',
            'contact_name': name,
            'email_from': post.get('email'),
            'phone': post.get('phone'),
            'partner_id': request.env.user.partner_id.id if request.env.user.has_group('base.group_portal') else False,
            'bsi_city': location.bsi_city if location else False,
            'bsi_location_id': location.id if location else False,
            'bsi_preferred_date': post.get('date') or False,
            'bsi_notes': notes,
        })
        first_name = (name or '').split(' ')[0]
        return request.redirect('/salon/contact?submitted=1&name=%s' % first_name)
