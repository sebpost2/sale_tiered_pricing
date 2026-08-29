from odoo import api, fields, models


class SalePricingTier(models.Model):
    _name = "sale.pricing.tier"
    _description = "Sale Pricing Tier"
    _order = "min_qty asc"

    name = fields.Char(required=True)
    min_qty = fields.Float(string="Minimum Quantity", required=True, default=0.0)
    discount_percent = fields.Float(string="Discount (%)", required=True, default=0.0)

    def _trigger_line_rematch(self):
        lines = self.env["sale.order.line"].search([("state", "=", "draft")])
        lines.modified(["product_uom_qty"])

    @api.model_create_multi
    def create(self, vals_list):
        tiers = super().create(vals_list)
        tiers._trigger_line_rematch()
        return tiers

    def write(self, vals):
        res = super().write(vals)
        if "min_qty" in vals:
            self._trigger_line_rematch()
        return res

    def unlink(self):
        lines = self.env["sale.order.line"].search([("tier_id", "in", self.ids)])
        res = super().unlink()
        lines.modified(["product_uom_qty"])
        return res
