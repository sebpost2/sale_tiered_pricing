from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    tier_id = fields.Many2one(
        "sale.pricing.tier",
        string="Applied Pricing Tier",
        compute="_compute_tier_id",
        store=True,
    )
    discount = fields.Float(
        digits="Discount",
        compute="_compute_discount_from_tier",
        store=True,
        readonly=False,
    )

    @api.depends("product_uom_qty")
    def _compute_tier_id(self):
        tiers = self.env["sale.pricing.tier"].search([], order="min_qty desc")
        for line in self:
            matched = self.env["sale.pricing.tier"]
            for tier in tiers:
                if line.product_uom_qty >= tier.min_qty:
                    matched = tier
                    break
            line.tier_id = matched

    @api.depends("tier_id", "tier_id.discount_percent")
    def _compute_discount_from_tier(self):
        for line in self:
            line.discount = line.tier_id.discount_percent if line.tier_id else 0.0
