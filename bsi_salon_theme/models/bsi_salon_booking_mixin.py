from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BsiSalonBookingMixin(models.AbstractModel):
    """Booking-shape fields shared by crm.lead (the booking's source of truth before the
    lead is Won) and bsi.salon.booking.request (the appointment, which only starts existing
    once Won). Field names are identical on both concrete models so copying one to the other
    at Won-time is a trivial 1:1 dict read, and slot-capacity checking can run identically on
    either side without duplicating the chair/artist/flat-capacity logic twice.

    email/phone field names differ between the two concrete models (crm.lead's own
    email_from/phone vs. bsi.salon.booking.request's bsi_email/bsi_phone), so those and the
    @api.depends/@api.constrains decorators that need them stay as thin per-model wrappers —
    only the actual lookup/validation bodies below are shared.
    """
    _name = 'bsi.salon.booking.mixin'
    _description = 'Salon Booking Details (shared by CRM Lead and Appointment)'

    bsi_location_id = fields.Many2one('bsi.salon.location', string='Branch')
    bsi_packages_enabled = fields.Boolean(
        compute='_compute_bsi_feature_flags',
        help='Mirrors Settings > Salon Management > Show Packages — the Package field is '
             'hidden here entirely whenever that\'s switched off, same as its backend menu.')
    bsi_membership_feature_enabled = fields.Boolean(
        compute='_compute_bsi_feature_flags',
        help='Mirrors Settings > Salon Management > Show Membership.')
    bsi_package_id = fields.Many2one(
        'bsi.salon.package', string='Package',
        help='Choosing a package replaces individual service selection — its own included '
             'services are auto-filled below, and the quotation is priced at the package '
             'total rather than the sum of each service\'s own price.')
    bsi_service_ids = fields.Many2many(
        'bsi.salon.service', string='Services', help='One or more services for this appointment. '
             'Not used when a Package is chosen — its own included services apply instead.')
    bsi_chair_ids = fields.Many2many(
        'bsi.salon.chair', string='Chairs',
        help='Chair/station options are limited to the selected branch and the categories of '
             'the selected services.')
    bsi_artist_id = fields.Many2one(
        'bsi.salon.team.member', string='Artist',
        help='Assigning an artist may add a flat surcharge (in ₹) to the total charge.')
    bsi_preferred_date = fields.Date(string='Booking Date')
    bsi_use_slot = fields.Boolean(
        string='Use Fixed Slot', default=True,
        help='Internal booking mode. New bookings use a predefined time slot by default.')
    bsi_use_custom_time = fields.Boolean(
        string='Use Custom Time', compute='_compute_bsi_use_custom_time',
        inverse='_inverse_bsi_use_custom_time', store=True,
        help='Enable only when this booking needs a time outside the configured time slots.')
    bsi_preferred_time = fields.Float(
        string='Custom Time', help='Used when "Use Custom Time" is enabled.')
    bsi_slot_id = fields.Many2one(
        'bsi.salon.time.slot', string='Time Slot', help='Default choice for a booking time.')
    # Labeled distinctly from crm.lead's own native "Notes" (its description field) — both
    # end up shown on the lead's form, so they need different labels to tell them apart.
    bsi_notes = fields.Text(string='Booking Notes')
    bsi_reference_image = fields.Image(
        string='Reference Image', max_width=1920, max_height=1920,
        help='Optional style/reference photo uploaded for this appointment.')
    bsi_referral_code_used = fields.Char(
        string='Referral Code Used',
        help="A friend's referral code entered on the booking form — resolved to a real "
             'referrer and stamped onto the new customer record only the first time a '
             "partner is created for them (see bsi.salon.booking.request._bsi_ensure_partner) "
             'so it never overwrites an existing customer\'s history.')

    bsi_has_membership = fields.Boolean(
        string='Has Active Membership', compute='_compute_bsi_has_membership',
        help='Whether the current email/phone matches a genuinely active subscription at '
             'all — drives whether "Apply membership discount" is even shown, so the option '
             'never appears for a customer who has nothing to apply.')
    bsi_is_member = fields.Boolean(
        string='Apply Membership Discount',
        help='Customer\'s own claim, ticked on the website. Only actually applied once verified '
             '(see bsi_membership_id) against a genuinely active subscription for their email.')
    bsi_membership_id = fields.Many2one(
        'bsi.salon.membership', string='Verified Membership', compute='_compute_bsi_amounts',
        store=True, readonly=True, copy=False,
        help='Set only when bsi_is_member is ticked AND the customer\'s email matches a '
             'genuinely active membership subscription — never trusts the checkbox alone.')
    bsi_discount_percent = fields.Float(
        string='Membership Discount %', compute='_compute_bsi_amounts', store=True)
    bsi_membership_perks = fields.Text(
        related='bsi_membership_id.bsi_perks', string='Plan Includes', readonly=True,
        help='Shown once bsi_membership_id is actually set (i.e. verified, not just ticked) '
             'so whoever is looking at the booking sees at a glance what the customer\'s '
             'plan entitles them to, not just the discount percentage.')
    bsi_services_amount = fields.Float(
        string='Services Amount', compute='_compute_bsi_amounts', store=True)
    bsi_amount_total = fields.Float(
        string='Total Amount', compute='_compute_bsi_amounts', store=True,
        help='Services amount plus the assigned artist\'s flat surcharge (if any) and any '
             'verified membership discount.')

    # ── Overridden per concrete model (different field names for email/phone) ──
    def _bsi_get_contact_email(self):
        self.ensure_one()
        return False

    def _bsi_get_contact_phone(self):
        self.ensure_one()
        return False

    def _bsi_find_active_subscriptions(self):
        """Active (not-yet-expired) subscriptions matching this record's own contact email
        or phone — shared by the discount computation below and by the "does this contact
        even have a membership" check that controls whether the "Apply membership discount"
        checkbox is shown at all (see bsi_has_membership)."""
        self.ensure_one()
        email = self._bsi_get_contact_email()
        phone = self._bsi_get_contact_phone()
        if not (email or phone):
            return self.env['bsi.salon.membership.subscription']
        contact_domain = [('bsi_partner_id.email', '=', email)] if email \
            else [('bsi_partner_id.phone', '=', phone)]
        today = fields.Date.context_today(self)
        return self.env['bsi.salon.membership.subscription'].sudo().search(contact_domain + [
            ('bsi_state', '=', 'active'), ('bsi_end_date', '>=', today),
        ])

    def _bsi_compute_bsi_amounts_common(self):
        for record in self:
            if record.bsi_package_id:
                # A package is a fixed bundle deal — its price is the price, regardless of
                # which artist ends up doing the work, unlike an individual-service booking
                # where the artist's own flat surcharge still applies.
                services_amount = record.bsi_package_id._bsi_get_effective_price()
                subtotal = services_amount
            else:
                services_amount = sum(s._bsi_get_effective_price() for s in record.bsi_service_ids)
                subtotal = services_amount + (record.bsi_artist_id.bsi_charge_amount or 0.0)
            record.bsi_services_amount = services_amount

            # A customer could hold more than one active tier at once (different
            # subscriptions), so pick whichever gives the best discount — search's order=
            # can't sort by a related field's sub-field, so this is done in Python instead.
            membership = self.env['bsi.salon.membership']
            if record.bsi_is_member:
                subs = record._bsi_find_active_subscriptions()
                if subs:
                    membership = max(subs.mapped('bsi_membership_id'), key=lambda m: m.bsi_discount_percent)

            record.bsi_membership_id = membership.id if membership else False
            record.bsi_discount_percent = membership.bsi_discount_percent if membership else 0.0
            record.bsi_amount_total = subtotal * (1 - record.bsi_discount_percent / 100.0)

    def _bsi_compute_has_membership_common(self):
        for record in self:
            record.bsi_has_membership = bool(record._bsi_find_active_subscriptions())

    @api.depends('bsi_use_slot')
    def _compute_bsi_use_custom_time(self):
        for record in self:
            record.bsi_use_custom_time = not record.bsi_use_slot

    def _inverse_bsi_use_custom_time(self):
        for record in self:
            record.bsi_use_slot = not record.bsi_use_custom_time

    @api.depends()
    def _compute_bsi_feature_flags(self):
        # Not keyed off any record field — these mirror a global Settings toggle, so every
        # record shares the same answer, freshly read from ir.config_parameter each time
        # (never stored, so a record fetched in a new request always sees the current value).
        ICP = self.env['ir.config_parameter'].sudo()
        packages_enabled = ICP.get_param('bsi_salon_theme.show_packages', 'True') == 'True'
        membership_enabled = ICP.get_param('bsi_salon_theme.show_membership', 'True') == 'True'
        for record in self:
            record.bsi_packages_enabled = packages_enabled
            record.bsi_membership_feature_enabled = membership_enabled

    def _bsi_check_use_slot_common(self):
        for record in self:
            if record.bsi_use_slot and not record.bsi_slot_id:
                # CRM leads are allowed to remain incomplete enquiries until staff marks
                # them Won. At that point crm.lead validates the selected time explicitly.
                if record._name == 'crm.lead' and not record.stage_id.is_won:
                    continue
                raise ValidationError(_('Select a time slot, or enable "Use Custom Time" to enter a custom time.'))

    def _bsi_onchange_package_common(self):
        # Package-exclusive: picking one replaces whatever individual services were chosen,
        # and clearing it back out just leaves the service picker empty again rather than
        # guessing what the customer might still want.
        for record in self:
            record.bsi_service_ids = record.bsi_package_id.bsi_service_ids

    def _bsi_check_package_exclusive_common(self):
        for record in self:
            if record.bsi_package_id and record.bsi_service_ids != record.bsi_package_id.bsi_service_ids:
                raise ValidationError(_(
                    'A package already includes its own services — remove the package to pick '
                    'individual services instead, or clear the services to use the package\'s own.'))

    def _bsi_slot_conflict_eligible(self):
        """Whether this record's own current state should participate in a capacity check at
        all — overridden per model (bsi.salon.booking.request keys this off bsi_state,
        crm.lead off `active`, since the two models use different conventions for
        "no longer live")."""
        self.ensure_one()
        return True

    def _bsi_slot_conflict_domains(self):
        """Shared domain-building for every slot-conflict check below — a pending lead
        'holds' a slot exactly like a confirmed appointment does, so both models are always
        checked together. Returns (lead_domain, appt_domain, Lead, Appointment), or None if
        this record isn't in a state where a conflict even applies (no fixed slot chosen,
        cancelled/inactive, etc)."""
        self.ensure_one()
        record = self
        if not (record.bsi_use_slot and record.bsi_slot_id
                and record.bsi_preferred_date and record._bsi_slot_conflict_eligible()):
            return None

        Lead = self.env['crm.lead'].sudo()
        Appointment = self.env['bsi.salon.booking.request'].sudo()
        lead_domain = [
            ('bsi_slot_id', '=', record.bsi_slot_id.id),
            ('bsi_preferred_date', '=', record.bsi_preferred_date),
            ('bsi_location_id', '=', record.bsi_location_id.id),
            ('active', '=', True),
            ('bsi_appointment_id', '=', False),
        ]
        appt_domain = [
            ('bsi_slot_id', '=', record.bsi_slot_id.id),
            ('bsi_preferred_date', '=', record.bsi_preferred_date),
            ('bsi_location_id', '=', record.bsi_location_id.id),
            ('bsi_state', '!=', 'cancelled'),
        ]
        if record._name == 'crm.lead':
            lead_domain.append(('id', '!=', record.id))
        else:
            appt_domain.append(('id', '!=', record.id))
            # An appointment is created FROM its originating lead (see
            # crm.lead._bsi_create_appointment_from_lead) by copying that lead's own
            # slot/chair/artist onto the new appointment, and only linking
            # bsi_appointment_id back onto the lead a moment later — so at the instant
            # this constraint fires (right after create()), that lead still looks like
            # an unconverted, still-pending claim on the very same slot and would
            # otherwise register as a conflict with itself. Exclude it explicitly.
            if record.bsi_crm_lead_id:
                lead_domain.append(('id', '!=', record.bsi_crm_lead_id.id))
        return lead_domain, appt_domain, Lead, Appointment

    def _bsi_get_chair_conflict_reason(self):
        """A physical chair can only serve one client at a time — the one real physical
        constraint that's still a hard, always-enforced block (see
        _bsi_check_slot_capacity_common below); unlike the artist/capacity check below, this
        one is never just advisory, since two customers physically cannot sit in the same
        chair at the same time regardless of anyone's intent to reschedule around it."""
        self.ensure_one()
        domains = self._bsi_slot_conflict_domains()
        if not domains or not self.bsi_chair_ids:
            return False
        lead_domain, appt_domain, Lead, Appointment = domains
        clashing_lead = Lead.search(lead_domain + [('bsi_chair_ids', 'in', self.bsi_chair_ids.ids)], limit=1)
        clashing_appt = Appointment.search(appt_domain + [('bsi_chair_ids', 'in', self.bsi_chair_ids.ids)], limit=1)
        clashing = clashing_lead or clashing_appt
        if clashing:
            shared_chair = (clashing.bsi_chair_ids & self.bsi_chair_ids)[:1]
            return _(
                '%s is already booked for the "%s" slot on %s. Please choose another chair or time.'
            ) % (shared_chair.name or _('That chair'), self.bsi_slot_id.name, self.bsi_preferred_date)
        return False

    def _bsi_get_artist_capacity_conflict_reason(self):
        """Artist-specific conflicts only — deliberately NOT a hard block (see
        _bsi_check_slot_capacity_common, which only checks chairs). Surfaced only at Won
        time as an advisory signal driving a reschedule wizard/email to the customer (see
        crm.lead._bsi_create_appointment_from_lead and action_set_won), since an artist
        preference is a soft constraint a human can resolve by offering a different time —
        unlike a chair, which is a real, non-negotiable physical resource. "No preference"
        bookings have no flat per-slot cap to share, so they never conflict here."""
        self.ensure_one()
        domains = self._bsi_slot_conflict_domains()
        if not domains or not self.bsi_artist_id:
            return False
        lead_domain, appt_domain, Lead, Appointment = domains
        # A specific stylist can only be in one place at a time — independent of how many
        # *other* artists already have bookings in the same slot.
        conflict = (
            Lead.search_count(lead_domain + [('bsi_artist_id', '=', self.bsi_artist_id.id)])
            or Appointment.search_count(appt_domain + [('bsi_artist_id', '=', self.bsi_artist_id.id)])
        )
        if conflict:
            return _(
                '%s is already booked for the "%s" slot on %s. Please choose another stylist or time.'
            ) % (self.bsi_artist_id.name, self.bsi_slot_id.name, self.bsi_preferred_date)
        return False

    def _bsi_check_slot_capacity_common(self):
        # Chair only — artist/flat-capacity conflicts are no longer a hard block anywhere
        # (see _bsi_get_artist_capacity_conflict_reason's docstring for why).
        for record in self:
            reason = record._bsi_get_chair_conflict_reason()
            if reason:
                raise ValidationError(reason)
