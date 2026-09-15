from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    bsi_appointment_id = fields.Many2one(
        'bsi.salon.booking.request', string='Salon Appointment', readonly=True, copy=False,
        help='Appointment this quotation was generated from.')
    bsi_location_id = fields.Many2one(
        related='bsi_appointment_id.bsi_location_id', string='Branch', readonly=True)
    bsi_artist_id = fields.Many2one(
        related='bsi_appointment_id.bsi_artist_id', string='Stylist', readonly=True)
    bsi_chair_ids = fields.Many2many(
        related='bsi_appointment_id.bsi_chair_ids', string='Chair(s)', readonly=True)
    bsi_preferred_date = fields.Date(
        related='bsi_appointment_id.bsi_preferred_date', string='Booking Date', readonly=True)
    bsi_appointment_time = fields.Char(
        string='Booking Time', compute='_compute_bsi_appointment_time')
    bsi_membership_id = fields.Many2one(
        related='bsi_appointment_id.bsi_membership_id', string='Membership Plan', readonly=True)
    bsi_discount_percent = fields.Float(
        related='bsi_appointment_id.bsi_discount_percent', string='Membership Discount %', readonly=True)
    bsi_membership_perks = fields.Text(
        related='bsi_membership_id.bsi_perks', string='Plan Includes', readonly=True)
    bsi_appointment_state = fields.Selection(
        related='bsi_appointment_id.bsi_state', string='Booking Status', readonly=True)
    bsi_rating_count = fields.Integer(
        related='bsi_appointment_id.rating_count', string='Review Count', readonly=True)
    bsi_rating_avg = fields.Float(
        related='bsi_appointment_id.rating_avg', string='Rating Average', readonly=True)

    @api.depends('bsi_appointment_id.bsi_use_slot', 'bsi_appointment_id.bsi_slot_id',
                 'bsi_appointment_id.bsi_preferred_time')
    def _compute_bsi_appointment_time(self):
        for order in self:
            appointment = order.bsi_appointment_id
            if appointment.bsi_use_slot and appointment.bsi_slot_id:
                order.bsi_appointment_time = appointment.bsi_slot_id.name
            elif appointment.bsi_preferred_time:
                hours, minutes = divmod(round(appointment.bsi_preferred_time * 60), 60)
                order.bsi_appointment_time = '%02d:%02d' % (hours, minutes)
            else:
                order.bsi_appointment_time = False

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

    # ── Review & Rating — only ever meaningful once the originating appointment is Done
    # (bsi_state == 'completed'), which itself only happens once its invoice is fully paid
    # (see bsi.salon.booking.request.action_complete / account.move's auto-Done check) — so
    # gating on that one state already means "Done AND fully paid", nothing extra to check.
    # Both buttons simply delegate to the appointment's own rating actions/data, so there's
    # one single source of truth for a booking's reviews whether staff opens it from the
    # Sale Order or from the Appointment itself. ──
    def action_bsi_open_appointment_ratings(self):
        self.ensure_one()
        return self.bsi_appointment_id.action_open_ratings()

    def action_bsi_add_appointment_review(self):
        self.ensure_one()
        return self.bsi_appointment_id.action_bsi_add_review()

    # ── Membership purchases: stock Odoo's own choke point for turning a *paid* website
    # order into a confirmed sale is action_confirm() (payment_transaction._post_process()
    # -> _check_amount_and_confirm_order() -> action_confirm(), same call a staff member's
    # manual "Confirm" click makes on a backend quotation) — so this is the one reliable
    # place to detect "this order contains a membership purchase" regardless of how the
    # order got confirmed. ──
    def action_confirm(self):
        result = super().action_confirm()
        self._bsi_process_membership_lines()
        return result

    def action_cancel(self):
        result = super().action_cancel()
        self.env['bsi.salon.membership.subscription'].sudo().search(
            [('bsi_sale_order_id', 'in', self.ids)]).write({'bsi_state': 'cancelled'})
        return result

    def _bsi_process_membership_lines(self):
        Membership = self.env['bsi.salon.membership'].sudo()
        Subscription = self.env['bsi.salon.membership.subscription'].sudo()
        for order in self:
            for line in order.order_line.filtered('product_id'):
                membership = Membership.search([
                    '|', ('bsi_product_monthly_id', '=', line.product_id.id),
                         ('bsi_product_yearly_id', '=', line.product_id.id),
                ], limit=1)
                if not membership:
                    continue
                billing_period = 'monthly' if membership.bsi_product_monthly_id.id == line.product_id.id else 'yearly'
                Subscription._bsi_create_or_extend(order.partner_id, membership, billing_period, line)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # A distinct field from the native "Disc.%" (discount) so it's visibly clear, line by
    # line, how much of the applied discount is the customer's membership rather than a
    # one-off manual discount a staff member might add on top — see
    # bsi_salon_booking_request.py._bsi_create_quotation, which sets both this and discount
    # together when a line is first created from a verified membership. Editing this field
    # feeds straight into the real "discount" field below (the one field Odoo's own pricing
    # engine actually reads), so the totals/taxes update exactly the same way a native
    # discount edit would — no separate price computation to maintain.
    bsi_membership_discount_percent = fields.Float(string='Membership Disc.%')

    @api.onchange('bsi_membership_discount_percent')
    def _onchange_bsi_membership_discount_percent(self):
        for line in self:
            line.discount = line.bsi_membership_discount_percent
