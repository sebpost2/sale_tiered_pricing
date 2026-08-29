from odoo import fields, models


class SalePricingTier(models.Model):
    _name = "sale.pricing.tier"
    _description = "Sale Pricing Tier"
    _order = "min_qty asc"

    name = fields.Char(required=True)
    min_qty = fields.Float(string="Minimum Quantity", required=True, default=0.0)
    discount_percent = fields.Float(string="Discount (%)", required=True, default=0.0)
    sequence = fields.Integer(default=10)
