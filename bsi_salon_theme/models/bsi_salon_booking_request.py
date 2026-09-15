import random

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BsiSalonBookingRequest(models.Model):
    _name = 'bsi.salon.booking.request'
    _description = 'Salon Appointment'
    # rating.mixin already inherits mail.thread itself — listing 'mail.thread' again
    # separately here caused an MRO conflict, so it's omitted (still fully present).
    # bsi.salon.booking.mixin supplies the booking-shape fields (branch, services, chair,
    # artist, date/slot, notes, reference image, membership discount) shared with crm.lead —
    # an appointment only ever comes into being once its originating lead is Won, copying
    # those same fields across (see crm_lead.py:_bsi_create_appointment_from_lead).
    _inherit = ['mail.activity.mixin', 'rating.mixin', 'bsi.salon.booking.mixin']
    _order = 'create_date desc'
    _rec_name = 'bsi_name'

    # ── Customer: either email or phone is enough to book (see
    # _check_bsi_contact_method below) — neither the name nor a linked partner is required. ──
    bsi_name = fields.Char(string='Full Name')
    bsi_email = fields.Char(string='Email')
    bsi_phone = fields.Char(string='Phone')
    bsi_partner_id = fields.Many2one(
        'res.partner', string='Customer', copy=False,
        help='Pick an existing customer, or type a new name to create one on the fly — fills '
             'in the name/email/phone below when they\'re blank. Left blank here, the '
             'customer is matched (by email or phone) or created automatically once the '
             'quotation is generated.')

    # ── City / Branch ────────────────────────────────────────────────────
    # bsi_city is a pure UI convenience for the website wizard's step-1 city picker (narrows
    # the branch dropdown) — not part of the shared mixin since crm.lead has no equivalent
    # step-by-step wizard UI. bsi_location_id itself comes from the mixin.
    bsi_city = fields.Selection(selection='_selection_bsi_city', string='City')

    # ── Legacy free-text fields from older website forms, kept for old records only ──
    bsi_service = fields.Char(string='Requested Service (legacy)',
                               help='Free-text service used by older website forms; new '
                                    'appointments should use the Services field instead.')
    bsi_chair_no = fields.Integer(string='Chair Number (legacy)')
    bsi_time_slot = fields.Char(string='Time Slot (legacy)',
                                 help='Free-text time slot used by older website forms.')

    bsi_artist_charge_amount = fields.Float(
        related='bsi_artist_id.bsi_charge_amount', string='Artist Surcharge', readonly=True)

    bsi_user_id = fields.Many2one(
        'res.users', string='Assigned To', default=lambda self: self.env.user,
        help='Staff member this appointment is assigned to. Used for user-wise filtering.')

    # ── Flow: draft → started/ended (visit in progress) → completed (Done, sale order
    # finalized). An appointment starts life in Draft the moment its lead is Won — there is
    # no separate "Booked" confirmation step; Start moves it straight into the visit.
    # group_expand is required for the kanban to show columns in this exact workflow order —
    # left to its own devices, Odoo's read_group sorts Selection-field groups alphabetically
    # by the raw stored key (cancelled, completed, draft, ended, started), not by the
    # selection list's own declared order. It also means every column always shows even when
    # a state currently has zero records, instead of columns appearing/disappearing with data. ──
    bsi_state = fields.Selection(
        [('draft', 'Draft'), ('started', 'Started'),
         ('ended', 'Ended'), ('completed', 'Done'), ('cancelled', 'Cancelled')],
        string='Status', default='draft', required=True, tracking=True, copy=False,
        group_expand='_bsi_group_expand_states')

    @api.model
    def _bsi_group_expand_states(self, states, domain):
        return [key for key, _label in self._fields['bsi_state'].selection]
    bsi_started_at = fields.Datetime(string='Started At', readonly=True, copy=False)
    bsi_ended_at = fields.Datetime(string='Ended At', readonly=True, copy=False)
    bsi_is_paused = fields.Boolean(string='Paused', readonly=True, copy=False)
    bsi_paused_at = fields.Datetime(string='Paused At', readonly=True, copy=False)
    bsi_service_line_ids = fields.One2many(
        'bsi.salon.booking.service.line', 'bsi_booking_id', string='Service Timings',
        help='One line per service, created automatically when the visit Starts. Each is '
             'started/ended independently, and every one must be Ended before the '
             'appointment itself can End (see action_end).')
    bsi_slot_start_time = fields.Float(
        related='bsi_slot_id.bsi_start_time', string='Slot Start Time', readonly=True)
    bsi_slot_end_time = fields.Float(
        related='bsi_slot_id.bsi_end_time', string='Slot End Time', readonly=True)
    bsi_crm_lead_id = fields.Many2one('crm.lead', string='CRM Lead', readonly=True, copy=False)
    bsi_sale_order_id = fields.Many2one(
        'sale.order', string='Quotation / Sale Order', readonly=True, copy=False)
    bsi_invoice_count = fields.Integer(compute='_compute_bsi_invoice_count')
    bsi_loyalty_awarded = fields.Boolean(
        default=False, copy=False,
        help='Guards against a double award — set the one time this appointment\'s loyalty '
             'points (and, where applicable, its referrer\'s bonus) are actually granted.')

    # ── Selections / domains ────────────────────────────────────────────
    @api.onchange('bsi_partner_id')
    def _onchange_bsi_partner_id(self):
        # Only fills in blanks — never overwrites a name/email/phone staff already typed,
        # e.g. for a customer calling in under a different number than the one on file.
        if self.bsi_partner_id:
            self.bsi_name = self.bsi_name or self.bsi_partner_id.name
            self.bsi_email = self.bsi_email or self.bsi_partner_id.email
            self.bsi_phone = self.bsi_phone or self.bsi_partner_id.phone

    def _selection_bsi_city(self):
        cities = self.env['bsi.salon.location'].sudo().search([]).mapped('bsi_city')
        return [(city, city) for city in sorted(set(filter(None, cities)))]

    # ── Note: the "Branch limited to City" / "Artist and Chairs limited to Branch" behavior
    # is now driven entirely by static, reactive `domain=` attributes on the fields
    # themselves in the view (referencing the sibling field by name, e.g.
    # domain="[('bsi_city', '=', bsi_city)]") — NOT by a `{'domain': ...}` dict returned from
    # an @api.onchange method. That legacy mechanism is silently ignored by Odoo's onchange
    # dispatch here (BaseModel._apply_onchange_methods only ever reads a returned method's
    # 'value'/'warning' keys, never 'domain'), so returning one from here would do nothing.
    # These onchange methods still exist for their other, still-functional side effects:
    # syncing bsi_city and clearing a now-mismatched artist/chairs when the branch changes. ──
    @api.onchange('bsi_city')
    def _onchange_bsi_city(self):
        if self.bsi_location_id and self.bsi_city and self.bsi_location_id.bsi_city != self.bsi_city:
            self.bsi_location_id = False

    @api.onchange('bsi_location_id')
    def _onchange_bsi_location_id(self):
        if self.bsi_location_id:
            self.bsi_city = self.bsi_location_id.bsi_city
            if self.bsi_artist_id.bsi_location_id and self.bsi_artist_id.bsi_location_id != self.bsi_location_id:
                self.bsi_artist_id = False

    @api.onchange('bsi_service_ids')
    def _onchange_bsi_service_ids(self):
        categories = self.bsi_service_ids.mapped('bsi_category')
        if categories:
            invalid_chairs = self.bsi_chair_ids.filtered(
                lambda chair: chair.bsi_service_category not in categories)
            self.bsi_chair_ids -= invalid_chairs

    @api.onchange('bsi_package_id')
    def _onchange_bsi_package_id(self):
        self._bsi_onchange_package_common()

    # ── Compute / contact accessors (feed the mixin's shared membership-discount logic) ──
    def _bsi_get_contact_email(self):
        self.ensure_one()
        return self.bsi_email

    def _bsi_get_contact_phone(self):
        self.ensure_one()
        return self.bsi_phone

    @api.depends('bsi_service_ids.bsi_price_amount', 'bsi_service_ids.bsi_price',
                 'bsi_artist_id.bsi_charge_amount', 'bsi_is_member', 'bsi_email', 'bsi_phone',
                 'bsi_package_id.bsi_bundle_price_amount', 'bsi_package_id.bsi_bundle_price')
    def _compute_bsi_amounts(self):
        self._bsi_compute_bsi_amounts_common()

    @api.depends('bsi_email', 'bsi_phone')
    def _compute_bsi_has_membership(self):
        self._bsi_compute_has_membership_common()

    @api.depends('bsi_sale_order_id.invoice_ids')
    def _compute_bsi_invoice_count(self):
        for appointment in self:
            appointment.bsi_invoice_count = len(appointment.bsi_sale_order_id.invoice_ids)

    # ── Constraints ──────────────────────────────────────────────────────
    @api.constrains('bsi_email', 'bsi_phone')
    def _check_bsi_contact_method(self):
        for appointment in self:
            if not (appointment.bsi_email or appointment.bsi_phone):
                raise ValidationError(_('Please provide an email or a phone number so we can reach you.'))

    @api.constrains('bsi_use_slot', 'bsi_slot_id')
    def _check_bsi_use_slot(self):
        self._bsi_check_use_slot_common()

    @api.constrains('bsi_package_id', 'bsi_service_ids')
    def _check_bsi_package_exclusive(self):
        self._bsi_check_package_exclusive_common()

    def _bsi_slot_conflict_eligible(self):
        self.ensure_one()
        return self.bsi_state != 'cancelled'

    @api.constrains('bsi_slot_id', 'bsi_preferred_date', 'bsi_location_id', 'bsi_state', 'bsi_use_slot',
                     'bsi_artist_id', 'bsi_chair_ids')
    def _check_bsi_slot_capacity(self):
        self._bsi_check_slot_capacity_common()

    def _bsi_ensure_partner(self):
        Partner = self.env['res.partner'].sudo()
        for appointment in self:
            if appointment.bsi_partner_id:
                continue
            partner = False
            if appointment.bsi_email:
                partner = Partner.search([('email', '=', appointment.bsi_email)], limit=1)
            if not partner and appointment.bsi_phone:
                partner = Partner.search([('phone', '=', appointment.bsi_phone)], limit=1)
            # Name is optional (booking only needs an email or a phone — see
            # _check_bsi_contact_method), so a name-less booking still needs a usable partner
            # name to create one with: falls back to whichever of email/phone was given,
            # which _check_bsi_contact_method guarantees is never both blank.
            partner_name = appointment.bsi_name or appointment.bsi_email or appointment.bsi_phone
            if not partner and partner_name:
                # Referred-by is only ever stamped here, at the moment a brand-new customer
                # record is actually created — never on a partner that already existed, so an
                # existing customer's own referral history can't be overwritten just because
                # they happened to book again through someone else's link.
                referrer = False
                if appointment.bsi_referral_code_used:
                    referrer = Partner.search([('bsi_referral_code', '=', appointment.bsi_referral_code_used)], limit=1)
                partner = Partner.create({
                    'name': partner_name,
                    'email': appointment.bsi_email,
                    'phone': appointment.bsi_phone,
                    'bsi_referred_by_id': referrer.id if referrer else False,
                })
            if partner:
                appointment.bsi_partner_id = partner.id

    def _bsi_create_quotation(self):
        SaleOrder = self.env['sale.order'].sudo()
        for appointment in self:
            if appointment.bsi_sale_order_id:
                continue
            appointment._bsi_ensure_partner()
            if not appointment.bsi_partner_id:
                continue

            # The appointment's own details (branch, date/time, stylist, chairs) are shown in
            # the quotation's header via the bsi_* related fields instead of as order lines —
            # every selected service is priced normally. One gets created on the fly if it has
            # no product linked yet, and its price falls back to the number in its price label
            # (e.g. "From ₹499") if no explicit amount was set, so quotations are never short a
            # line or a total just because that setup step was skipped.
            # Sequence starts well above the default (10) that "Add a product"/"Catalog" gives
            # any retail product added afterward, so those always sort above the appointment's
            # own service lines regardless of when they're added — the total already combines
            # every line on the order automatically, no extra logic needed for that part.
            # discount uses the order line's own native field (not baked into price_unit) so
            # the original price stays visible/auditable on the quotation.
            if appointment.bsi_package_id:
                # Every included service still appears as its own line (so the customer sees
                # exactly what the package covers), but each is scaled down so the lines add
                # up to the package's own bundle price rather than the sum of each service's
                # normal price — a fixed bundle deal, not affected by the artist surcharge.
                services = appointment.bsi_package_id.bsi_service_ids
                full_price = sum(s._bsi_get_effective_price() for s in services)
                package_price = appointment.bsi_package_id._bsi_get_effective_price()
                scale = (package_price / full_price) if full_price else 1.0
                line_amounts = [service._bsi_get_effective_price() * scale for service in services]
                order_lines = [
                    (0, 0, {
                        'product_id': service.sudo()._bsi_get_or_create_product().id,
                        'name': service.name,
                        'product_uom_qty': 1,
                        'price_unit': amount,
                        'sequence': 1000 + index * 10,
                    })
                    for index, (service, amount) in enumerate(zip(services, line_amounts))
                ]
                discount_base = sum(line_amounts)
            else:
                line_amounts = [service._bsi_get_effective_price() for service in appointment.bsi_service_ids]
                order_lines = [
                    (0, 0, {
                        'product_id': service.sudo()._bsi_get_or_create_product().id,
                        'name': service.name,
                        'product_uom_qty': 1,
                        'price_unit': amount,
                        'sequence': 1000 + index * 10,
                    })
                    for index, (service, amount) in enumerate(zip(appointment.bsi_service_ids, line_amounts))
                ]
                # The artist's charge is a flat ₹ amount, not a per-service multiplier — it
                # gets its own single line rather than being folded into every service's price.
                charge_amount = appointment.bsi_artist_id.bsi_charge_amount or 0.0
                if charge_amount:
                    order_lines.append((0, 0, {
                        'product_id': appointment.bsi_artist_id.sudo()._bsi_get_or_create_surcharge_product().id,
                        'name': _('%s - Artist Surcharge') % appointment.bsi_artist_id.name,
                        'product_uom_qty': 1,
                        'price_unit': charge_amount,
                        'sequence': 1500,
                    }))
                discount_base = sum(line_amounts) + charge_amount

            # The membership discount applies once, to the visit's final total — not to
            # each service individually — so it's its own single line (a negative amount)
            # rather than a per-line "Disc.%" on every service, making it visibly clear on
            # the quotation as one deduction rather than N slightly-cheaper prices.
            if appointment.bsi_discount_percent:
                discount_amount = discount_base * appointment.bsi_discount_percent / 100.0
                discount_product = self.env.ref('bsi_salon_theme.bsi_salon_discount_product')
                order_lines.append((0, 0, {
                    'product_id': discount_product.id,
                    'name': _('Membership Discount (%s%%)') % int(appointment.bsi_discount_percent),
                    'product_uom_qty': 1,
                    'price_unit': -discount_amount,
                    'sequence': 2000,
                }))

            order = SaleOrder.create({
                'partner_id': appointment.bsi_partner_id.id,
                'origin': _('Salon Appointment - %s') % (
                    appointment.bsi_location_id.name or appointment.bsi_name or appointment.bsi_partner_id.name),
                'bsi_appointment_id': appointment.id,
                'order_line': order_lines,
            })
            appointment.bsi_sale_order_id = order.id
            if appointment.bsi_crm_lead_id:
                appointment.bsi_crm_lead_id.sudo().write({'partner_id': appointment.bsi_partner_id.id})

    # ── Workflow buttons: draft -> started -> ended -> completed(Done) ──
    def action_start(self):
        self.write({'bsi_state': 'started', 'bsi_started_at': fields.Datetime.now()})
        for appointment in self:
            appointment._bsi_create_service_lines()

    def action_pause(self):
        self.write({'bsi_is_paused': True, 'bsi_paused_at': fields.Datetime.now()})

    def action_resume(self):
        self.write({'bsi_is_paused': False})

    def _bsi_create_service_lines(self):
        """One line per service actually being performed, created once (idempotent) when the
        visit Starts, so each can be Started/Ended independently — see action_end's guard,
        which blocks completing the visit until every one of these is Ended."""
        Line = self.env['bsi.salon.booking.service.line'].sudo()
        for appointment in self:
            if appointment.bsi_service_line_ids:
                continue
            services = (appointment.bsi_package_id.bsi_service_ids
                        if appointment.bsi_package_id else appointment.bsi_service_ids)
            for service in services:
                Line.create({'bsi_booking_id': appointment.id, 'bsi_service_id': service.id})

    def action_end(self):
        # The quotation is generated here, once the visit itself is over — not at
        # Draft/Started, so nothing gets quoted for a service that might still change
        # mid-visit. It's deliberately left in Draft — confirming it (and, from there,
        # creating the invoice) is its own explicit step on the quotation itself, using
        # stock Sales/Invoicing (see the "Invoices" smart button below), not something this
        # button does automatically. Completion (Done) then follows once that invoice is
        # actually paid in full — see account.move._bsi_check_appointments_for_auto_done —
        # rather than being tied to this same button.
        for appointment in self:
            unfinished = appointment.bsi_service_line_ids.filtered(lambda l: l.bsi_state != 'ended')
            if unfinished:
                raise ValidationError(_(
                    'Every service must be Ended before the appointment can End — still '
                    'pending: %s.') % ', '.join(unfinished.mapped('bsi_service_id.name')))
        self.write({'bsi_state': 'ended', 'bsi_ended_at': fields.Datetime.now(), 'bsi_is_paused': False})
        for appointment in self:
            appointment._bsi_create_quotation()

    def action_complete(self):
        self.write({'bsi_state': 'completed'})
        self._bsi_maybe_award_loyalty_points()

    def _bsi_maybe_award_loyalty_points(self):
        """Awards loyalty points once BOTH halves of "appointment done and paid" are true —
        called from here (Done) and from account.move (payment confirmed), whichever happens
        second is what actually grants it. Also grants a one-time referral bonus to whoever
        referred this customer, but only on their first-ever awarded appointment — a repeat
        customer's later visits earn their own points as normal, never a second referral
        bonus for the same referrer."""
        Point = self.env['bsi.salon.loyalty.point'].sudo()
        for appointment in self:
            if appointment.bsi_loyalty_awarded or appointment.bsi_state != 'completed':
                continue
            partner = appointment.bsi_partner_id
            order = appointment.bsi_sale_order_id
            if not partner or not order:
                continue
            if not any(invoice.payment_state in ('paid', 'in_payment') for invoice in order.invoice_ids):
                continue

            Point.create({
                'bsi_partner_id': partner.id,
                'bsi_points': random.randint(1, 20),
                'bsi_reason': 'appointment',
                'bsi_appointment_id': appointment.id,
            })
            appointment.bsi_loyalty_awarded = True

            if partner.bsi_referred_by_id:
                prior_awards = Point.search_count([
                    ('bsi_partner_id', '=', partner.id), ('bsi_reason', '=', 'appointment'),
                ])
                if prior_awards == 1:  # the one just created above — this is their first
                    Point.create({
                        'bsi_partner_id': partner.bsi_referred_by_id.id,
                        'bsi_points': 100,
                        'bsi_reason': 'referral',
                        'bsi_appointment_id': appointment.id,
                        'bsi_referred_partner_id': partner.id,
                    })

    def action_cancel(self):
        for appointment in self:
            if appointment.bsi_sale_order_id and appointment.bsi_sale_order_id.state in ('draft', 'sent'):
                appointment.bsi_sale_order_id.sudo().action_cancel()
            if appointment.bsi_crm_lead_id:
                appointment.bsi_crm_lead_id.sudo().active = False
        self.write({'bsi_state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'bsi_state': 'draft'})

    # ── Smart buttons ────────────────────────────────────────────────────
    def action_bsi_view_crm_lead(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'CRM Lead', 'res_model': 'crm.lead',
            'res_id': self.bsi_crm_lead_id.id, 'view_mode': 'form', 'target': 'current',
        }

    def action_bsi_view_quotation(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': 'Quotation', 'res_model': 'sale.order',
            'res_id': self.bsi_sale_order_id.id, 'view_mode': 'form', 'target': 'current',
        }

    def action_bsi_view_invoices(self):
        self.ensure_one()
        invoices = self.bsi_sale_order_id.invoice_ids
        action = {
            'type': 'ir.actions.act_window', 'name': _('Invoices'), 'res_model': 'account.move',
            'view_mode': 'list,form', 'domain': [('id', 'in', invoices.ids)],
        }
        if len(invoices) == 1:
            action.update(view_mode='form', res_id=invoices.id)
        return action

    def action_open_ratings(self):
        """Smart-button target: the ratings already on this appointment (jumps straight to
        the form if there's only one) — mirrors project.task's own action_open_ratings. Uses
        bsi_salon_rating_view_form (not the stock rating.rating form, which hides `rating`
        entirely and has no artist fields at all) for the form view either way."""
        self.ensure_one()
        form_view = self.env.ref('bsi_salon_theme.bsi_salon_rating_view_form')
        action = {
            'type': 'ir.actions.act_window', 'name': _('Ratings'), 'res_model': 'rating.rating',
            'view_mode': 'list,form', 'views': [(False, 'list'), (form_view.id, 'form')],
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': self._bsi_rating_create_context(),
        }
        if self.rating_count == 1:
            action.update(view_mode='form', res_id=self.rating_ids.id)
        return action

    def action_bsi_add_review(self):
        """"Add Review" button on the Reviews & Ratings tab — opens a blank rating.rating
        record pre-linked to this appointment (and pre-filled with its customer/artist),
        rather than relying on the rating_ids inverse field to infer that on its own."""
        self.ensure_one()
        form_view = self.env.ref('bsi_salon_theme.bsi_salon_rating_view_form')
        return {
            'type': 'ir.actions.act_window', 'name': _('Add Review'), 'res_model': 'rating.rating',
            'view_mode': 'form', 'views': [(form_view.id, 'form')], 'target': 'new',
            'context': self._bsi_rating_create_context(),
        }

    def _bsi_rating_create_context(self):
        # rating.rating's own `res_model` is a readonly related field (derived from
        # res_model_id, an ir.model Many2one) with no write-through inverse — passing
        # default_res_model directly is silently ignored, so the actual ir.model record
        # must be resolved and passed as default_res_model_id instead.
        self.ensure_one()
        return {
            'default_res_model_id': self.env['ir.model']._get(self._name).id,
            'default_res_id': self.id,
            'default_consumed': True,
            'default_partner_id': self.bsi_partner_id.id,
            'default_bsi_artist_id': self.bsi_artist_id.id,
        }

    def _bsi_submit_review(self, rating_value, artist_rating_value, feedback):
        """Create or update this appointment's customer review — one review per (appointment,
        customer) pair, so resubmitting from the portal just edits the existing rating.rating
        record instead of piling up duplicates. Ownership (this is really the appointment's
        own customer) and eligibility (bsi_state == 'completed', i.e. the visit is fully paid)
        are checked by the caller — see controllers/portal.py's review route — not here."""
        self.ensure_one()
        Rating = self.env['rating.rating'].sudo()
        existing = Rating.search([
            ('res_model', '=', self._name), ('res_id', '=', self.id),
            ('partner_id', '=', self.bsi_partner_id.id),
        ], limit=1)
        vals = {
            'rating': rating_value,
            'bsi_artist_id': self.bsi_artist_id.id,
            'bsi_artist_rating': artist_rating_value,
            'feedback': feedback,
            'consumed': True,
            'partner_id': self.bsi_partner_id.id,
        }
        if existing:
            existing.write(vals)
            return existing
        vals.update({
            'res_model_id': self.env['ir.model']._get(self._name).id,
            'res_id': self.id,
        })
        return Rating.create(vals)
