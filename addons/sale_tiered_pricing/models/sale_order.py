from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    margin_guard_min_percent = fields.Float(
        string="Minimum Margin (%)",
        related="company_id.margin_guard_min_percent",
        readonly=False,
    )
    margin_guard_triggered = fields.Boolean(
        string="Margin Guard Triggered",
        compute="_compute_margin_guard",
        store=True,
    )
    margin_guard_message = fields.Char(
        string="Margin Guard Message",
        compute="_compute_margin_guard",
        store=True,
    )

    @api.depends("margin_percent", "margin_guard_min_percent", "order_line")
    def _compute_margin_guard(self):
        for order in self:
            min_percent = order.margin_guard_min_percent
            actual_percent = order.margin_percent * 100
            if min_percent and order.order_line and actual_percent < min_percent:
                order.margin_guard_triggered = True
                order.margin_guard_message = (
                    "Margin %.1f%% is below the configured minimum of %.1f%%."
                    % (actual_percent, min_percent)
                )
            else:
                order.margin_guard_triggered = False
                order.margin_guard_message = False
