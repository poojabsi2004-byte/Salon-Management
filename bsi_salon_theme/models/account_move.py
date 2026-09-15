from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _compute_payment_state(self):
        # payment_state is itself a stored COMPUTED field — it's set here, during a
        # recompute flush (e.g. after registering a payment), never through a plain
        # write({'payment_state': ...}) call from application code, so overriding write()
        # instead of this method would silently never fire.
        previous_by_id = {move.id: move.payment_state for move in self}
        super()._compute_payment_state()
        newly_paid = self.filtered(
            lambda m: m.payment_state in ('paid', 'in_payment')
            and m.payment_state != previous_by_id.get(m.id))
        if newly_paid:
            newly_paid._bsi_check_appointments_for_loyalty_points()
            newly_paid._bsi_check_appointments_for_auto_done()

    def _bsi_check_appointments_for_auto_done(self):
        """Once an Ended appointment's invoice is fully paid, the visit is complete in
        every sense that matters — move it to Done automatically rather than waiting on a
        separate manual click. action_complete itself still exists as a manual fallback
        (e.g. a walk-in paid in cash outside the normal invoice flow)."""
        appointments = self.env['bsi.salon.booking.request']
        for move in self:
            orders = move.invoice_line_ids.sale_line_ids.order_id
            appointments |= orders.mapped('bsi_appointment_id')
        ended = appointments.filtered(lambda a: a.bsi_state == 'ended')
        if ended:
            ended.sudo().action_complete()

    def _bsi_check_appointments_for_loyalty_points(self):
        """A salon appointment's loyalty points require BOTH the appointment being marked
        Done and its invoice being fully paid — whichever of the two happens second is what
        actually triggers the award (see bsi.salon.booking.request._bsi_maybe_award_loyalty_points,
        which is idempotent and safe to call again from either side)."""
        appointments = self.env['bsi.salon.booking.request']
        for move in self:
            orders = move.invoice_line_ids.sale_line_ids.order_id
            appointments |= orders.mapped('bsi_appointment_id')
        if appointments:
            appointments.sudo()._bsi_maybe_award_loyalty_points()
