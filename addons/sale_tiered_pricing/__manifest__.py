{
    "name": "Tiered Pricing & Margin Guard",
    "version": "19.0.1.0.0",
    "summary": "Volume discount tiers on quotations with a margin guard and a custom QWeb report.",
    "description": """
Applies volume discount tiers automatically to sale order lines based on
quantity, and flags quotations whose aggregate margin falls below a
configurable minimum.
""",
    "author": "Sebastian Postigo",
    "license": "LGPL-3",
    "category": "Sales",
    "depends": ["sale", "sale_margin"],
    "data": [
        "security/ir.model.access.csv",
        "views/pricing_tier_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
}
