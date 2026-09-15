from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    # bsi.salon.booking.mixin supplies the booking-shape fields (branch, services, chair,
    # artist, date/slot, notes, reference image, membership discount) — a website booking
    # (or a phone-in one staff enter by hand) lives here, on the lead, as the actual source
    # of truth, from the moment it's submitted right up until the lead is Won. Only then does
    # an appointment get created (see _bsi_create_appointment_from_lead below), by copying
    # these same fields across (same names on both models, so it's a straight 1:1 copy).
    _name = 'crm.lead'
    _inherit = ['crm.lead', 'bsi.salon.booking.mixin']

    bsi_appointment_id = fields.Many2one(
        'bsi.salon.booking.request', string='Salon Appointment', readonly=True, copy=False,
        help='Appointment created automatically once this lead is Won, carrying over the '
             'branch/services/chair/artist/date/slot entered here.')
    bsi_appointment_state = fields.Selection(
        related='bsi_appointment_id.bsi_state', string='Booking Status')
    bsi_appointment_time = fields.Char(
        string='Booking Time', compute='_compute_bsi_appointment_time')
    bsi_stage_is_won = fields.Boolean(related='stage_id.is_won')
    bsi_city = fields.Selection(
        selection='_selection_bsi_city', string='City',
        help='City selected before choosing the salon branch for this booking.')

    def _selection_bsi_city(self):
        cities = self.env['bsi.salon.location'].sudo().search([]).mapped('bsi_city')
        return [(city, city) for city in sorted(set(filter(None, cities)))]

    # ── Note: "Branch limited to City" / "Artist and Chairs limited to Branch" is driven by
    # static, reactive `domain=` attributes on the fields themselves in the view (referencing
    # a sibling field by name) — NOT by a `{'domain': ...}` dict returned from an
    # @api.onchange method, which Odoo's onchange dispatch here silently ignores
    # (BaseModel._apply_onchange_methods only reads a returned method's 'value'/'warning'
    # keys, never 'domain'). These onchange methods still exist for their other, still-
    # functional side effects: syncing bsi_city and clearing a now-mismatched
    # artist/chairs when the branch changes. ──
    @api.onchange('bsi_city')
    def _onchange_bsi_city(self):
        for lead in self:
            if (lead.bsi_location_id and lead.bsi_city
                    and lead.bsi_location_id.bsi_city != lead.bsi_city):
                lead.bsi_location_id = False

    @api.onchange('bsi_location_id')
    def _onchange_bsi_location_id(self):
        for lead in self:
            if lead.bsi_location_id:
                lead.bsi_city = lead.bsi_location_id.bsi_city
                if lead.bsi_artist_id.bsi_location_id and lead.bsi_artist_id.bsi_location_id != lead.bsi_location_id:
                    lead.bsi_artist_id = False

    @api.onchange('bsi_service_ids')
    def _onchange_bsi_service_ids(self):
        categories = self.bsi_service_ids.mapped('bsi_category')
        if categories:
            invalid_chairs = self.bsi_chair_ids.filtered(
                lambda chair: chair.bsi_service_category not in categories)
            self.bsi_chair_ids -= invalid_chairs

    def _bsi_validate_won_booking_details(self):
        """A lead may be saved as an enquiry with partial details, but it cannot become
        a confirmed sale until its appointment can be created unambiguously."""
        for lead in self:
            missing = []
            if not (lead.bsi_service_ids or lead.bsi_package_id):
                missing.append(_('Services'))
            if not lead.bsi_city:
                missing.append(_('City'))
            if not lead.bsi_location_id:
                missing.append(_('Branch'))
            if not lead.bsi_preferred_date:
                missing.append(_('Booking Date'))
            if lead.bsi_use_slot:
                if not lead.bsi_slot_id:
                    missing.append(_('Time Slot'))
            elif not lead.bsi_preferred_time:
                missing.append(_('Booking Time'))
            if missing:
                raise ValidationError(_(
                    'Complete the Booking Details before marking this lead Won: %s.')
                    % ', '.join(missing))

    @api.depends('bsi_use_slot', 'bsi_slot_id', 'bsi_preferred_time')
    def _compute_bsi_appointment_time(self):
        for lead in self:
            if lead.bsi_use_slot and lead.bsi_slot_id:
                lead.bsi_appointment_time = lead.bsi_slot_id.name
            elif lead.bsi_preferred_time:
                hours, minutes = divmod(round(lead.bsi_preferred_time * 60), 60)
                lead.bsi_appointment_time = '%02d:%02d' % (hours, minutes)
            else:
                lead.bsi_appointment_time = False

    # ── Compute / conflict accessors (feed the mixin's shared membership-discount and
    # slot-capacity logic) ──────────────────────────────────────────────────────────
    def _bsi_get_contact_email(self):
        self.ensure_one()
        return self.email_from

    def _bsi_get_contact_phone(self):
        self.ensure_one()
        return self.phone

    def _bsi_slot_conflict_eligible(self):
        self.ensure_one()
        return self.active

    @api.depends('bsi_service_ids.bsi_price_amount', 'bsi_service_ids.bsi_price',
                 'bsi_artist_id.bsi_charge_amount', 'bsi_is_member', 'email_from', 'phone',
                 'bsi_package_id.bsi_bundle_price_amount', 'bsi_package_id.bsi_bundle_price')
    def _compute_bsi_amounts(self):
        self._bsi_compute_bsi_amounts_common()

    @api.depends('email_from', 'phone')
    def _compute_bsi_has_membership(self):
        self._bsi_compute_has_membership_common()

    @api.onchange('bsi_package_id')
    def _onchange_bsi_package_id(self):
        self._bsi_onchange_package_common()

    @api.constrains('bsi_use_slot', 'bsi_slot_id')
    def _check_bsi_use_slot(self):
        self._bsi_check_use_slot_common()

    @api.constrains('bsi_package_id', 'bsi_service_ids')
    def _check_bsi_package_exclusive(self):
        self._bsi_check_package_exclusive_common()

    @api.constrains('bsi_slot_id', 'bsi_preferred_date', 'bsi_location_id', 'active', 'bsi_use_slot',
                     'bsi_artist_id', 'bsi_chair_ids')
    def _check_bsi_slot_capacity(self):
        # Bypassed for exactly the leads write() below has already identified as conflicted
        # going into a Won transition — those are handled gracefully (email instead of a
        # raised error) by _bsi_create_appointment_from_lead/_bsi_notify_slot_conflict
        # instead, once this same write has gone through.
        if self.env.context.get('bsi_skip_slot_capacity_check'):
            return
        self._bsi_check_slot_capacity_common()

    # ── Appointment created only once this lead reaches a Won stage — never before. ──
    @api.model_create_multi
    def create(self, vals_list):
        leads = super().create(vals_list)
        leads._bsi_create_appointment_from_lead()
        return leads

    def write(self, vals):
        conflicted = self.browse()
        if 'stage_id' in vals:
            new_stage = self.env['crm.stage'].browse(vals['stage_id'])
            if new_stage.is_won:
                self.filtered(lambda l: not l.stage_id.is_won and not l.bsi_appointment_id)._bsi_validate_won_booking_details()
                # Odoo re-validates @api.constrains on ANY write to the record, not only
                # when one of its own watched fields is in `vals` — so simply writing
                # stage_id here would otherwise let _check_bsi_slot_capacity raise and roll
                # back this entire write the instant the record flushes, well before
                # _bsi_create_appointment_from_lead below ever gets a chance to handle a
                # conflict gracefully. Pre-check now and bypass that one constraint just for
                # the leads that are already conflicted, so the Won transition itself still
                # goes through — the sale is still Won, only the specific appointment is
                # what's deferred pending a new time from the customer.
                conflicted = self.filtered(
                    lambda l: not l.bsi_appointment_id and l._bsi_get_artist_capacity_conflict_reason())

        clean = self - conflicted
        result = super(CrmLead, clean).write(vals) if clean else True
        if conflicted:
            result = super(CrmLead, conflicted.with_context(bsi_skip_slot_capacity_check=True)).write(vals) and result
        if 'stage_id' in vals:
            self._bsi_create_appointment_from_lead()
        return result

    def _bsi_create_appointment_from_lead(self):
        Appointment = self.env['bsi.salon.booking.request'].sudo()
        for lead in self:
            if lead.bsi_appointment_id or not lead.stage_id.is_won:
                continue
            lead._bsi_validate_won_booking_details()
            # The lead's own chair/artist/slot claim is normally airtight (any OTHER booking
            # that would conflict with it is blocked at ITS OWN creation time by the same
            # constraint) — but a slot can still turn out taken by the time a lead reaches
            # Won, e.g. staff editing another record with elevated access, or a narrow
            # concurrent-request race. Rather than let that raise a ValidationError and roll
            # back the whole Won transaction (a confusing, work-blocking error for whoever
            # just clicked "Won"), gracefully email the customer instead and leave this lead
            # without an appointment — the next save once the slot/artist/chair is corrected
            # retries this same method automatically (see write() above).
            conflict_reason = lead._bsi_get_artist_capacity_conflict_reason()
            if conflict_reason:
                lead._bsi_notify_slot_conflict(conflict_reason)
                continue
            appointment = Appointment.create({
                'bsi_name': lead.contact_name or lead.partner_id.name or lead.name,
                'bsi_email': lead.email_from,
                'bsi_phone': lead.phone,
                'bsi_partner_id': lead.partner_id.id if lead.partner_id else False,
                'bsi_location_id': lead.bsi_location_id.id,
                'bsi_city': lead.bsi_city,
                'bsi_package_id': lead.bsi_package_id.id,
                'bsi_service_ids': [(6, 0, lead.bsi_service_ids.ids)],
                'bsi_chair_ids': [(6, 0, lead.bsi_chair_ids.ids)],
                'bsi_artist_id': lead.bsi_artist_id.id,
                'bsi_preferred_date': lead.bsi_preferred_date,
                'bsi_use_slot': lead.bsi_use_slot,
                'bsi_preferred_time': lead.bsi_preferred_time,
                'bsi_slot_id': lead.bsi_slot_id.id,
                'bsi_notes': lead.bsi_notes,
                'bsi_referral_code_used': lead.bsi_referral_code_used,
                'bsi_reference_image': lead.bsi_reference_image,
                'bsi_is_member': lead.bsi_is_member,
                'bsi_crm_lead_id': lead.id,
                'bsi_user_id': lead.user_id.id if lead.user_id else False,
                # Starts in Draft (the field's own default) — there is no separate "Booked"
                # confirmation step; Start is what actually moves the visit forward.
            })
            lead.bsi_appointment_id = appointment.id

    def _bsi_notify_slot_conflict(self, reason):
        self.ensure_one()
        template = self.env.ref(
            'bsi_salon_theme.bsi_salon_slot_conflict_mail_template', raise_if_not_found=False)
        if template and self._bsi_get_contact_email():
            template.sudo().send_mail(self.id, force_send=False, email_layout_xmlid='mail.mail_notification_light')
        self.message_post(body=_(
            'Could not create the appointment: %s The customer has been emailed to pick a new time.'
        ) % reason)
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_('Salon slot no longer available — pick a new time with the customer'),
            note=reason,
            user_id=self.user_id.id or self.env.uid,
        )

    def action_set_won(self):
        # The interactive counterpart to write()'s silent email fallback above: clicking
        # "Won" (the form/kanban button, not a drag-and-drop — see the wizard's own
        # docstring for why this only covers the button) on a lead whose artist/slot has
        # since been taken opens a wizard instead of marking it Won outright, so a human can
        # immediately pick and send a same-day alternative rather than finding out only
        # after the fact via the emailed notice. Any OTHER, non-conflicted leads in the same
        # call (e.g. a multi-select mass action) still go through the normal Won flow.
        self.filtered(lambda l: not l.bsi_appointment_id)._bsi_validate_won_booking_details()
        conflicted = self.filtered(
            lambda l: not l.bsi_appointment_id and l._bsi_get_artist_capacity_conflict_reason())
        clean = self - conflicted
        result = super(CrmLead, clean).action_set_won() if clean else True
        if conflicted:
            lead = conflicted[0]
            return {
                'type': 'ir.actions.act_window',
                'name': _('Slot No Longer Available'),
                'res_model': 'bsi.salon.reschedule.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_lead_id': lead.id,
                    'default_conflict_reason': lead._bsi_get_artist_capacity_conflict_reason(),
                },
            }
        return result

    def action_bsi_retry_appointment(self):
        """Manual retry for staff after fixing a lead's chair/artist/slot following a
        conflict notification (see _bsi_notify_slot_conflict) — re-runs the exact same
        Won-time appointment-creation attempt without needing another stage_id write."""
        self._bsi_create_appointment_from_lead()

    def action_bsi_view_appointment(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Booking',
            'res_model': 'bsi.salon.booking.request',
            'res_id': self.bsi_appointment_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

