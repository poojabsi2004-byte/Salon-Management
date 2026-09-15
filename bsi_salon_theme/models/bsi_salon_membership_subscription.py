from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _


class BsiSalonMembershipSubscription(models.Model):
    _name = 'bsi.salon.membership.subscription'
    _description = 'Salon Membership Subscription'
    _inherit = ['mail.thread']
    _order = 'bsi_start_date desc, id desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    bsi_partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True,
        default=lambda self: self.env.user.partner_id)
    bsi_membership_id = fields.Many2one(
        'bsi.salon.membership', string='Membership Tier', required=True, index=True, ondelete='restrict')
    bsi_billing_period = fields.Selection(
        [('monthly', 'Monthly'), ('yearly', 'Yearly')], string='Billing Period',
        required=True, default='monthly', tracking=True)
    # Defaults to today and is auto-activated on save (see create() below) — a manually
    # created subscription is assumed already agreed/paid (e.g. an offline/cash payment
    # recorded by staff), so it goes straight to Active rather than sitting in Draft. The
    # real website-purchase path (_bsi_create_or_extend) already creates one Active
    # directly, without ever touching create()'s auto-activation (see the filter there).
    bsi_start_date = fields.Date(string='Active From', tracking=True, default=fields.Date.context_today)
    bsi_end_date = fields.Date(string='Expires On', tracking=True)
    bsi_state = fields.Selection(
        [('draft', 'Draft'), ('active', 'Active'), ('expired', 'Expired'), ('cancelled', 'Cancelled')],
        string='Status', default='draft', required=True, tracking=True, copy=False)
    bsi_sale_order_id = fields.Many2one(
        'sale.order', string='Sale Order', readonly=True, copy=False,
        help='Most recent order that created or renewed this subscription (blank for one '
             'activated manually in the backend, e.g. an offline/cash payment).')
    bsi_amount_paid = fields.Float(
        string='Amount Paid', copy=False,
        help='Auto-filled from the tier\'s price for the chosen billing period when activated '
             '(snapshot of the order line total instead, for a subscription created via a real '
             'website purchase — not the whole order, since the cart may also contain unrelated '
             'shop products).')

    @api.depends('bsi_partner_id', 'bsi_membership_id', 'bsi_billing_period')
    def _compute_name(self):
        for sub in self:
            period_label = dict(sub._fields['bsi_billing_period'].selection).get(sub.bsi_billing_period, '')
            sub.name = '%s — %s (%s)' % (sub.bsi_partner_id.name or _('Unknown'),
                                          sub.bsi_membership_id.name or _('Membership'), period_label)

    def _bsi_compute_end_date(self, billing_period, start_date):
        delta = relativedelta(months=1) if billing_period == 'monthly' else relativedelta(years=1)
        return start_date + delta

    @api.onchange('bsi_membership_id', 'bsi_billing_period', 'bsi_start_date')
    def _onchange_bsi_membership_preview(self):
        # Live preview only — create() below is what actually guarantees these are set,
        # so this just lets staff see the real expiry/price before saving.
        for sub in self:
            if not sub.bsi_membership_id:
                continue
            start_date = sub.bsi_start_date or fields.Date.context_today(sub)
            sub.bsi_end_date = sub._bsi_compute_end_date(sub.bsi_billing_period, start_date)
            membership = sub.bsi_membership_id
            sub.bsi_amount_paid = (membership.bsi_price_monthly if sub.bsi_billing_period == 'monthly'
                                    else membership.bsi_price_yearly * 12)

    # ── Workflow: draft -> active -> expired/cancelled ──────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        subscriptions = super().create(vals_list)
        # _bsi_create_or_extend (the real website-purchase path) already creates its records
        # directly in 'active' with the correct order-derived amount/dates — this only ever
        # catches ones still sitting in 'draft', i.e. a plain backend "New" — so customer +
        # plan alone are enough to get a fully activated subscription on save, no separate
        # "Activate" click needed.
        subscriptions.filtered(lambda s: s.bsi_state == 'draft').action_activate()
        # Covers a subscription created ALREADY active (e.g. _bsi_create_or_extend's "brand
        # new tier" branch) — write() below only ever sees a *transition* into 'active', not
        # one set at creation time, so this is the one path that needs handling separately.
        subscriptions.filtered(lambda s: s.bsi_state == 'active')._bsi_cancel_other_active_subscriptions()
        return subscriptions

    def write(self, vals):
        result = super().write(vals)
        # Catches every OTHER way a subscription can become Active — the statusbar widget's
        # own click-to-set-stage (bypasses action_activate() entirely), action_activate()
        # itself (which calls write() internally), and _bsi_create_or_extend's "extend an
        # existing one" branch — one single choke point instead of duplicating this in each.
        if vals.get('bsi_state') == 'active':
            self._bsi_cancel_other_active_subscriptions()
        return result

    def _bsi_cancel_other_active_subscriptions(self):
        """Only one membership tier can ever be active for a given customer at a time —
        activating a different tier (Silver while Gold is still active, say) automatically
        cancels whatever else was active for them, rather than leaving two active side by
        side. Same tier being renewed/extended is a no-op here (nothing else to cancel)."""
        for sub in self:
            if sub.bsi_state != 'active' or not sub.bsi_partner_id or not sub.bsi_membership_id:
                continue
            others = self.sudo().search([
                ('bsi_partner_id', '=', sub.bsi_partner_id.id),
                ('bsi_membership_id', '!=', sub.bsi_membership_id.id),
                ('bsi_state', '=', 'active'),
                ('id', '!=', sub.id),
            ])
            if others:
                others.write({'bsi_state': 'cancelled'})

    def action_activate(self):
        """Manual/backend activation (e.g. staff recording an offline payment) — computes the
        exact same start/end dates the real website-payment path (_bsi_create_or_extend)
        computes, and auto-fills the price from the tier if nothing more specific was set."""
        for sub in self:
            start_date = sub.bsi_start_date or fields.Date.context_today(sub)
            vals = {
                'bsi_state': 'active',
                'bsi_start_date': start_date,
                'bsi_end_date': sub._bsi_compute_end_date(sub.bsi_billing_period, start_date),
            }
            if not sub.bsi_amount_paid:
                membership = sub.bsi_membership_id
                vals['bsi_amount_paid'] = (membership.bsi_price_monthly if sub.bsi_billing_period == 'monthly'
                                            else membership.bsi_price_yearly * 12)
            sub.write(vals)

    def action_cancel(self):
        self.write({'bsi_state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'bsi_state': 'draft'})

    def _cron_bsi_expire_subscriptions(self):
        today = fields.Date.context_today(self)
        self.search([('bsi_state', '=', 'active'), ('bsi_end_date', '<', today)]).write({'bsi_state': 'expired'})

    def _bsi_create_or_extend(self, partner, membership, billing_period, order_line):
        """Create a new (already-Active) subscription, or extend the customer's existing
        active/expired one for this same tier, idempotently against the same order line's
        order (so re-processing an already-confirmed order never double-extends). A Draft
        subscription for the same partner+tier is deliberately left alone — it was never
        actually paid for, so a real payment creates its own separate Active record rather
        than silently repurposing an unrelated pending draft."""
        Subscription = self.sudo()
        already_processed = Subscription.search([
            ('bsi_membership_id', '=', membership.id),
            ('bsi_sale_order_id', '=', order_line.order_id.id),
        ], limit=1)
        if already_processed:
            return already_processed

        today = fields.Date.context_today(self)
        existing = Subscription.search([
            ('bsi_partner_id', '=', partner.id),
            ('bsi_membership_id', '=', membership.id),
            ('bsi_state', 'in', ('active', 'expired')),
        ], order='bsi_end_date desc', limit=1)

        vals = {
            'bsi_billing_period': billing_period,
            'bsi_state': 'active',
            'bsi_sale_order_id': order_line.order_id.id,
            'bsi_amount_paid': order_line.price_total,
        }
        if existing:
            base_date = max(existing.bsi_end_date, today)
            existing.write({**vals, 'bsi_end_date': self._bsi_compute_end_date(billing_period, base_date)})
            return existing
        return Subscription.create({
            **vals,
            'bsi_partner_id': partner.id,
            'bsi_membership_id': membership.id,
            'bsi_start_date': today,
            'bsi_end_date': self._bsi_compute_end_date(billing_period, today),
        })
