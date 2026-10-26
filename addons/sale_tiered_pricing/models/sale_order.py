from odoo import _, api, fields, models


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
    # Not stored: built when read, so each user gets it in their own language.
    margin_guard_message = fields.Char(
        string="Margin Guard Message",
        compute="_compute_margin_guard_message",
    )

    @api.depends("margin_percent", "margin_guard_min_percent", "order_line")
    def _compute_margin_guard(self):
        for order in self:
            min_percent = order.margin_guard_min_percent
            order.margin_guard_triggered = bool(
                min_percent and order.order_line and order.margin_percent * 100 < min_percent
            )

    @api.depends("margin_guard_triggered", "margin_percent", "margin_guard_min_percent")
    @api.depends_context("lang")
    def _compute_margin_guard_message(self):
        for order in self:
            order.margin_guard_message = order.margin_guard_triggered and _(
                "Margin %(actual).1f%% is below the configured minimum of %(minimum).1f%%.",
                actual=order.margin_percent * 100,
                minimum=order.margin_guard_min_percent,
            )
