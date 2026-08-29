from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    margin_guard_min_percent = fields.Float(
        string="Minimum Margin (%)",
        default=0.0,
        help="Quotations with an aggregate margin below this percentage are flagged. Set to 0 to disable.",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    margin_guard_min_percent = fields.Float(
        related="company_id.margin_guard_min_percent",
        readonly=False,
    )
