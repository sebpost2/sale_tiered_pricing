# Sale Tiered Pricing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `sale_tiered_pricing`, an installable Odoo 19 Community addon that applies volume discount tiers to quotation lines, flags quotes whose aggregate margin falls below a configurable minimum, extends the quotation PDF, and ships a real TransactionCase test suite.

**Architecture:** A single addon (`addons/sale_tiered_pricing/`) running against the official `odoo:19` Docker image + `postgres:16`, both defined in this repo's own `docker-compose.yml`. One new model (`sale.pricing.tier`, a global discount ladder), one inherited model field-group on `sale.order.line` (tier matching + discount), one inherited field-group on `sale.order`/`res.company` (aggregate margin guard, built on top of core `sale_margin`), and a QWeb report extension. Day 1 = Tasks 1-5 (environment through margin guard). Day 2 = Tasks 6-7 (report, README).

**Tech Stack:** Odoo 19 (Community), PostgreSQL 16, Docker Compose, Python (Odoo ORM), QWeb, `odoo.tests.TransactionCase`.

**Spec:** `D:\2_MyScripts\FINANCE\sale_tiered_pricing\docs\superpowers\specs\2026-08-28-sale-tiered-pricing-design.md`

## Global Constraints

- **Isolation (hard constraint):** Never read, copy, or reference anything under `D:\1_Working` (Enterprise-licensed Odoo source, employer/client proprietary modules). All Odoo source-syntax verification in this plan points at the *official `odoo:19` Docker image's own installed files* — never the local `_Core` copies.
- **Zero external dependencies.** No API keys, no network calls at runtime, no mocking. `depends` in the manifest is `["sale", "sale_margin"]` — both ship with stock Odoo Community.
- Reuse Odoo's native mechanisms instead of inventing parallel ones: tiers write to the **native** `sale.order.line.discount` field; margin math is delegated entirely to core `sale_margin` (`sale.order.margin_percent`) — this module never recomputes margin from scratch.
- Margin guard is **aggregate on `sale.order`**, not per-line (see spec: "Margin guard scope" decision).
- Tiers are a **global list**, not scoped to product or category (see spec: "why tiers live on their own model").
- The guard **flags, never blocks** — no `@api.constrains` preventing save.
- Every model file's compute methods need correct `@api.depends` — this is graded explicitly by whoever reviews the code, per the spec's stated goal.
- Commit after every task; message describes the behavior added, not the mechanics.

---

### Task 1: Docker Compose environment + empty module skeleton

**Files:**
- Create: `docker-compose.yml`
- Create: `addons/sale_tiered_pricing/__init__.py`
- Create: `addons/sale_tiered_pricing/__manifest__.py`
- Create: `addons/sale_tiered_pricing/models/__init__.py`
- Create: `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: a running Odoo 19 + Postgres 16 stack reachable at `localhost:8069`, with `addons/` mounted into the container at `/mnt/extra-addons`, and an installable (empty) `sale_tiered_pricing` module.

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: odoo
      POSTGRES_PASSWORD: odoo
      POSTGRES_DB: postgres
    volumes:
      - odoo-db-data:/var/lib/postgresql/data

  odoo:
    image: odoo:19
    depends_on:
      - db
    ports:
      - "8069:8069"
    environment:
      HOST: db
      USER: odoo
      PASSWORD: odoo
    volumes:
      - ./addons:/mnt/extra-addons
      - odoo-web-data:/var/lib/odoo

volumes:
  odoo-db-data:
  odoo-web-data:
```

- [ ] **Step 2: Write `.gitignore`**

```
.vscode/
*.pyc
__pycache__/
```

- [ ] **Step 3: Write the empty module skeleton**

`addons/sale_tiered_pricing/__manifest__.py`:

```python
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
    "data": [],
    "installable": True,
    "application": False,
}
```

`addons/sale_tiered_pricing/__init__.py`:

```python
from . import models
```

`addons/sale_tiered_pricing/models/__init__.py`:

```python
```

(empty file — populated in later tasks)

- [ ] **Step 4: Bring the stack up**

Run: `docker compose up -d`
Expected: both `db` and `odoo` containers report `running` in `docker compose ps`.

- [ ] **Step 5: Install the empty module to prove the pipeline works**

Run:
```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --stop-after-init --without-demo=all
```
Expected: log ends with `Modules loaded.` and no traceback. This confirms the addon is discovered, depends resolve against stock Community Odoo (`sale`, `sale_margin` — no Enterprise needed), and the container/volume wiring is correct.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml .gitignore addons/sale_tiered_pricing/__init__.py addons/sale_tiered_pricing/__manifest__.py addons/sale_tiered_pricing/models/__init__.py
git commit -m "chore: scaffold sale_tiered_pricing module and Docker Compose environment"
```

---

### Task 2: `sale.pricing.tier` model, security, configuration view

**Files:**
- Create: `addons/sale_tiered_pricing/models/pricing_tier.py`
- Modify: `addons/sale_tiered_pricing/models/__init__.py`
- Create: `addons/sale_tiered_pricing/security/ir.model.access.csv`
- Create: `addons/sale_tiered_pricing/views/pricing_tier_views.xml`
- Modify: `addons/sale_tiered_pricing/__manifest__.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `sale.pricing.tier` model with fields `name` (Char), `min_qty` (Float), `discount_percent` (Float), `sequence` (Integer). Read access for the base Sales user group, full access for Sales Manager. A list/form view reachable from Sales → Configuration → Pricing Tiers.

- [ ] **Step 1: Write the model**

`addons/sale_tiered_pricing/models/pricing_tier.py`:

```python
from odoo import fields, models


class SalePricingTier(models.Model):
    _name = "sale.pricing.tier"
    _description = "Sale Pricing Tier"
    _order = "min_qty asc"

    name = fields.Char(required=True)
    min_qty = fields.Float(string="Minimum Quantity", required=True, default=0.0)
    discount_percent = fields.Float(string="Discount (%)", required=True, default=0.0)
    sequence = fields.Integer(default=10)
```

- [ ] **Step 2: Wire it into `models/__init__.py`**

```python
from . import pricing_tier
```

- [ ] **Step 3: Write access rights**

`addons/sale_tiered_pricing/security/ir.model.access.csv`:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sale_pricing_tier_user,sale.pricing.tier.user,model_sale_pricing_tier,sales_team.group_sale_salesman,1,0,0,0
access_sale_pricing_tier_manager,sale.pricing.tier.manager,model_sale_pricing_tier,sales_team.group_sale_manager,1,1,1,1
```

- [ ] **Step 4: Write the configuration view**

`addons/sale_tiered_pricing/views/pricing_tier_views.xml`:

```xml
<odoo>
    <record id="view_sale_pricing_tier_list" model="ir.ui.view">
        <field name="name">sale.pricing.tier.list</field>
        <field name="model">sale.pricing.tier</field>
        <field name="arch" type="xml">
            <list string="Pricing Tiers" editable="bottom">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
                <field name="min_qty"/>
                <field name="discount_percent"/>
            </list>
        </field>
    </record>

    <record id="action_sale_pricing_tier" model="ir.actions.act_window">
        <field name="name">Pricing Tiers</field>
        <field name="res_model">sale.pricing.tier</field>
        <field name="view_mode">list,form</field>
    </record>

    <menuitem id="menu_sale_pricing_tier"
              name="Pricing Tiers"
              parent="sale.menu_sale_config"
              action="action_sale_pricing_tier"
              sequence="50"/>
</odoo>
```

Note: Odoo 19 uses the `<list>` tag (not the pre-17 `<tree>` tag) for list views. If `docker compose exec odoo odoo ... -i sale_tiered_pricing` errors on this view's arch, inspect the real, currently-installed `sale` module views inside the **official container** for the correct tag/attribute syntax — never the local `D:\1_Working` copies:
```bash
docker compose exec odoo find / -name "sale_order_views.xml" 2>/dev/null
docker compose exec odoo cat <path found above>
```

- [ ] **Step 5: Register the new data files in the manifest**

In `addons/sale_tiered_pricing/__manifest__.py`, change `"data": []` to:

```python
    "data": [
        "security/ir.model.access.csv",
        "views/pricing_tier_views.xml",
    ],
```

- [ ] **Step 6: Reinstall and verify in the browser**

Run:
```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --stop-after-init --without-demo=all
```
Expected: `Modules loaded.`, no traceback.

Then open `http://localhost:8069`, log in as admin on the `sale_tiered_pricing_test` database, go to Sales → Configuration → Pricing Tiers, and confirm you can create a tier (e.g. name "10+", min_qty 10, discount_percent 5) and it saves.

- [ ] **Step 7: Commit**

```bash
git add addons/sale_tiered_pricing/models/pricing_tier.py addons/sale_tiered_pricing/models/__init__.py addons/sale_tiered_pricing/security/ir.model.access.csv addons/sale_tiered_pricing/views/pricing_tier_views.xml addons/sale_tiered_pricing/__manifest__.py
git commit -m "feat: add sale.pricing.tier model, access rights, and configuration view"
```

---

### Task 3: Tier matching and discount computation on `sale.order.line`

**Files:**
- Create: `addons/sale_tiered_pricing/models/sale_order_line.py`
- Modify: `addons/sale_tiered_pricing/models/__init__.py`
- Create: `addons/sale_tiered_pricing/tests/__init__.py`
- Create: `addons/sale_tiered_pricing/tests/test_pricing_tier.py`

**Interfaces:**
- Consumes: `sale.pricing.tier` (Task 2).
- Produces: `sale.order.line.tier_id` (Many2one to `sale.pricing.tier`, computed, stored — the best-matching tier for the line's current quantity, or empty if none matches). Overrides the **native** `sale.order.line.discount` field to be computed from `tier_id.discount_percent`, while staying `readonly=False` so a user can still hand-edit it (same pattern Odoo core uses for `price_unit`).

- [ ] **Step 1: Write the failing tests**

`addons/sale_tiered_pricing/tests/__init__.py`:

```python
from . import test_pricing_tier
```

`addons/sale_tiered_pricing/tests/test_pricing_tier.py`:

```python
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPricingTier(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Test Customer"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Widget",
                "type": "consu",
                "list_price": 100.0,
                "standard_price": 60.0,
            }
        )
        cls.tier_10 = cls.env["sale.pricing.tier"].create(
            {"name": "10+", "min_qty": 10, "discount_percent": 5}
        )
        cls.tier_50 = cls.env["sale.pricing.tier"].create(
            {"name": "50+", "min_qty": 50, "discount_percent": 15}
        )

    def _create_order(self, qty, product=None):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": (product or self.product).id,
                "product_uom_qty": qty,
            }
        )
        return order, line

    def test_qty_below_first_tier_gets_no_discount(self):
        _, line = self._create_order(9)
        self.assertFalse(line.tier_id)
        self.assertEqual(line.discount, 0.0)

    def test_qty_exactly_at_tier_minimum_matches(self):
        _, line = self._create_order(10)
        self.assertEqual(line.tier_id, self.tier_10)
        self.assertEqual(line.discount, 5.0)

    def test_qty_one_above_tier_minimum_matches(self):
        _, line = self._create_order(11)
        self.assertEqual(line.tier_id, self.tier_10)

    def test_qty_one_below_next_tier_minimum_stays_on_lower_tier(self):
        _, line = self._create_order(49)
        self.assertEqual(line.tier_id, self.tier_10)
        self.assertNotEqual(line.tier_id, self.tier_50)

    def test_no_tiers_configured_gives_zero_discount(self):
        (self.tier_10 | self.tier_50).unlink()
        _, line = self._create_order(100)
        self.assertFalse(line.tier_id)
        self.assertEqual(line.discount, 0.0)

    def test_overlapping_tiers_highest_wins(self):
        _, line = self._create_order(75)
        self.assertEqual(line.tier_id, self.tier_50)
        self.assertEqual(line.discount, 15.0)

    def test_discount_recomputes_when_quantity_changes(self):
        _, line = self._create_order(5)
        self.assertEqual(line.discount, 0.0)
        line.product_uom_qty = 60
        self.assertEqual(line.tier_id, self.tier_50)
        self.assertEqual(line.discount, 15.0)
        line.product_uom_qty = 2
        self.assertFalse(line.tier_id)
        self.assertEqual(line.discount, 0.0)

    def test_rounding_at_currency_precision(self):
        product = self.env["product.product"].create(
            {
                "name": "Oddly Priced Widget",
                "type": "consu",
                "list_price": 33.335,
                "standard_price": 10.0,
            }
        )
        order, line = self._create_order(10, product=product)
        currency = order.currency_id
        expected = currency.round(line.price_unit * 10 * 0.95)
        self.assertEqual(currency.round(line.price_subtotal), expected)

    def test_editing_tier_discount_percent_updates_existing_lines(self):
        _, line = self._create_order(60)
        self.assertEqual(line.discount, 15.0)
        self.tier_50.discount_percent = 20.0
        self.assertEqual(line.discount, 20.0)

    def test_multiple_lines_match_independent_tiers(self):
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line_a = self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 5}
        )
        line_b = self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 60}
        )
        self.assertFalse(line_a.tier_id)
        self.assertEqual(line_b.tier_id, self.tier_50)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all
```
Expected: FAIL / traceback — `tier_id` does not exist on `sale.order.line` yet.

- [ ] **Step 3: Implement the model**

`addons/sale_tiered_pricing/models/sale_order_line.py`:

```python
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
```

- [ ] **Step 4: Wire it into `models/__init__.py`**

```python
from . import pricing_tier
from . import sale_order_line
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all
```
Expected: all 10 tests in `TestPricingTier` pass, no traceback.

- [ ] **Step 6: Commit**

```bash
git add addons/sale_tiered_pricing/models/sale_order_line.py addons/sale_tiered_pricing/models/__init__.py addons/sale_tiered_pricing/tests/
git commit -m "feat: match quantity tiers and apply discount on sale order lines"
```

---

### Task 4: Company-level margin guard threshold

**Files:**
- Create: `addons/sale_tiered_pricing/models/res_config_settings.py`
- Modify: `addons/sale_tiered_pricing/models/__init__.py`
- Create: `addons/sale_tiered_pricing/views/res_config_settings_views.xml`
- Modify: `addons/sale_tiered_pricing/__manifest__.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `res.company.margin_guard_min_percent` (Float, default 0.0 — 0 means "guard disabled"), exposed on `res.config.settings` as a related field, editable from Settings → Sales.

- [ ] **Step 1: Write the model**

`addons/sale_tiered_pricing/models/res_config_settings.py`:

```python
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
```

- [ ] **Step 2: Wire it into `models/__init__.py`**

```python
from . import pricing_tier
from . import sale_order_line
from . import res_config_settings
```

- [ ] **Step 3: Write the settings view**

`addons/sale_tiered_pricing/views/res_config_settings_views.xml`:

```xml
<odoo>
    <record id="res_config_settings_view_form_tiered_pricing" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.sale.tiered.pricing</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="sale.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//block[@id='sale_invoicing_setting_container']" position="after">
                <block title="Margin Guard" id="sale_tiered_pricing_setting_container">
                    <setting help="Quotations whose aggregate margin falls below this percentage are flagged.">
                        <field name="margin_guard_min_percent"/>
                    </setting>
                </block>
            </xpath>
        </field>
    </record>
</odoo>
```

If the xpath target `block[@id='sale_invoicing_setting_container']` does not exist in the installed Odoo 19 `sale` module's settings view, find the real block id inside the **official container**:
```bash
docker compose exec odoo find / -name "res_config_settings_views.xml" -path "*sale*" 2>/dev/null
docker compose exec odoo cat <path found above>
```
and update the `expr` to a real `id` from that file.

- [ ] **Step 4: Register the view in the manifest**

In `addons/sale_tiered_pricing/__manifest__.py`, add to `data`:

```python
        "views/res_config_settings_views.xml",
```

- [ ] **Step 5: Reinstall and verify in the browser**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --stop-after-init --without-demo=all
```
Then in the browser: Settings → Sales, confirm a "Margin Guard" section with a "Minimum Margin (%)" field appears and saves.

- [ ] **Step 6: Commit**

```bash
git add addons/sale_tiered_pricing/models/res_config_settings.py addons/sale_tiered_pricing/models/__init__.py addons/sale_tiered_pricing/views/res_config_settings_views.xml addons/sale_tiered_pricing/__manifest__.py
git commit -m "feat: add configurable company-level margin guard threshold"
```

---

### Task 5: Aggregate margin guard on `sale.order`

**Files:**
- Create: `addons/sale_tiered_pricing/models/sale_order.py`
- Modify: `addons/sale_tiered_pricing/models/__init__.py`
- Create: `addons/sale_tiered_pricing/views/sale_order_views.xml`
- Modify: `addons/sale_tiered_pricing/__manifest__.py`
- Modify: `addons/sale_tiered_pricing/tests/test_pricing_tier.py`

**Interfaces:**
- Consumes: `res.company.margin_guard_min_percent` (Task 4), core `sale.order.margin_percent` (from `sale_margin`).
- Produces: `sale.order.margin_guard_min_percent` (related, editable), `sale.order.margin_guard_triggered` (Boolean, computed, stored), `sale.order.margin_guard_message` (Char, computed, stored).

- [ ] **Step 1: Add the failing tests**

Append to `addons/sale_tiered_pricing/tests/test_pricing_tier.py` (inside the existing `TestPricingTier` class):

```python
    def test_margin_without_discount(self):
        _, line = self._create_order(1)
        self.assertAlmostEqual(line.order_id.margin_percent, 0.40, places=2)

    def test_margin_with_discount_lower_than_without(self):
        order_no_discount, _ = self._create_order(1)
        order_with_discount, _ = self._create_order(60)
        self.assertLess(order_with_discount.margin_percent, order_no_discount.margin_percent)

    def test_margin_guard_triggers_below_threshold(self):
        self.env.company.margin_guard_min_percent = 35.0
        order, _ = self._create_order(60)
        self.assertTrue(order.margin_guard_triggered)
        self.assertIn("35.0", order.margin_guard_message)

    def test_margin_guard_does_not_trigger_above_threshold(self):
        self.env.company.margin_guard_min_percent = 10.0
        order, _ = self._create_order(1)
        self.assertFalse(order.margin_guard_triggered)
        self.assertFalse(order.margin_guard_message)

    def test_margin_guard_disabled_when_threshold_zero(self):
        self.env.company.margin_guard_min_percent = 0.0
        order, _ = self._create_order(60)
        self.assertFalse(order.margin_guard_triggered)

    def test_multiline_order_guard_reflects_aggregate(self):
        self.env.company.margin_guard_min_percent = 25.0
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        healthy_product = self.env["product.product"].create(
            {"name": "High Margin", "type": "consu", "list_price": 100.0, "standard_price": 10.0}
        )
        self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": healthy_product.id, "product_uom_qty": 1}
        )
        self.env["sale.order.line"].create(
            {"order_id": order.id, "product_id": self.product.id, "product_uom_qty": 60}
        )
        self.assertFalse(order.margin_guard_triggered)

    def test_empty_order_does_not_trigger_guard(self):
        self.env.company.margin_guard_min_percent = 50.0
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        self.assertFalse(order.margin_guard_triggered)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all
```
Expected: FAIL — `margin_guard_triggered` does not exist on `sale.order` yet.

- [ ] **Step 3: Implement the model**

`addons/sale_tiered_pricing/models/sale_order.py`:

```python
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
```

**Note on `margin_percent` format:** core `sale_margin` stores `margin_percent` as a fraction (0.0-1.0), matching how Odoo's `widget="percentage"` fields are conventionally stored. `test_margin_without_discount` (list_price 100, standard_price 60 → 40% margin) will confirm this directly. If that test fails with a value 40x too large or too small, `margin_percent` is stored as a whole-number percent instead — remove the `* 100` in `actual_percent` above and adjust the test's expected value from `0.40` to `40.0` (and the `places=2` won't matter at that scale).

- [ ] **Step 4: Wire it into `models/__init__.py`**

```python
from . import pricing_tier
from . import sale_order_line
from . import res_config_settings
from . import sale_order
```

- [ ] **Step 5: Write the quotation form banner view**

`addons/sale_tiered_pricing/views/sale_order_views.xml`:

```xml
<odoo>
    <record id="view_order_form_margin_guard" model="ir.ui.view">
        <field name="name">sale.order.form.margin.guard</field>
        <field name="model">sale.order</field>
        <field name="inherit_id" ref="sale.view_order_form"/>
        <field name="arch" type="xml">
            <xpath expr="//sheet" position="before">
                <div class="alert alert-warning" role="alert"
                     invisible="not margin_guard_triggered">
                    <field name="margin_guard_message" readonly="1" nolabel="1"/>
                </div>
            </xpath>
        </field>
    </record>
</odoo>
```

If `//sheet` does not resolve inside the installed Odoo 19 `sale.view_order_form`, inspect the real view inside the **official container** (`docker compose exec odoo find / -name "sale_order_views.xml" 2>/dev/null`) and adjust the xpath target.

- [ ] **Step 6: Register the view in the manifest**

In `addons/sale_tiered_pricing/__manifest__.py`, add to `data`:

```python
        "views/sale_order_views.xml",
```

- [ ] **Step 7: Run the tests to verify they pass**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all
```
Expected: all 17 tests in `TestPricingTier` pass.

- [ ] **Step 8: Verify the banner in the browser**

Set Settings → Sales → Minimum Margin (%) to e.g. `35`, create a quotation with a line quantity that triggers a tier discount pushing margin below 35%, confirm the warning banner appears above the order lines.

- [ ] **Step 9: Commit**

```bash
git add addons/sale_tiered_pricing/models/sale_order.py addons/sale_tiered_pricing/models/__init__.py addons/sale_tiered_pricing/views/sale_order_views.xml addons/sale_tiered_pricing/__manifest__.py addons/sale_tiered_pricing/tests/test_pricing_tier.py
git commit -m "feat: aggregate margin guard on the quotation with a warning banner"
```

---

### Task 6: QWeb quotation report extension

**Files:**
- Create: `addons/sale_tiered_pricing/report/quotation_report.xml`
- Modify: `addons/sale_tiered_pricing/__manifest__.py`
- Modify: `addons/sale_tiered_pricing/tests/test_pricing_tier.py`

**Interfaces:**
- Consumes: `sale.order.line.tier_id` (Task 3).
- Produces: an inherited QWeb template extending `sale.report_saleorder_document` that shows the matched tier's name under a line's description when a tier applied.

- [ ] **Step 1: Add the failing test**

Append to `addons/sale_tiered_pricing/tests/test_pricing_tier.py`:

```python
    def test_quotation_report_renders_without_error(self):
        order, _ = self._create_order(60)
        report = self.env["ir.actions.report"]._get_report_from_name(
            "sale.report_saleorder"
        )
        content, _ = report._render_qweb_html(
            "sale.report_saleorder", order.ids
        )
        self.assertIn(b"50+", content)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all
```
Expected: FAIL — the rendered report does not yet contain the tier name.

- [ ] **Step 3: Implement the report extension**

`addons/sale_tiered_pricing/report/quotation_report.xml`:

```xml
<odoo>
    <template id="report_saleorder_document_tier_note" inherit_id="sale.report_saleorder_document">
        <xpath expr="//td[@name='td_name']" position="inside">
            <div t-if="line.tier_id" class="text-muted" style="font-size: 0.85em;">
                Volume discount applied: <span t-esc="line.tier_id.name"/>
            </div>
        </xpath>
    </template>
</odoo>
```

If `//td[@name='td_name']` does not exist in the installed Odoo 19 `sale.report_saleorder_document` template, find the real node inside the **official container**:
```bash
docker compose exec odoo find / -name "*.xml" -path "*sale*report*" 2>/dev/null
docker compose exec odoo cat <path found above>
```
and update the `expr` to target the actual line-description cell.

- [ ] **Step 4: Register the report in the manifest**

In `addons/sale_tiered_pricing/__manifest__.py`, add to `data`:

```python
        "report/quotation_report.xml",
```

- [ ] **Step 5: Run the test to verify it passes**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all
```
Expected: all 18 tests pass.

- [ ] **Step 6: Verify the PDF in the browser**

Open the quotation created in Step 8 of Task 5 (or create a new one with a tier-matching quantity), click Print → PDF, confirm the "Volume discount applied: 50+" note appears under that line.

- [ ] **Step 7: Commit**

```bash
git add addons/sale_tiered_pricing/report/quotation_report.xml addons/sale_tiered_pricing/__manifest__.py addons/sale_tiered_pricing/tests/test_pricing_tier.py
git commit -m "feat: show applied pricing tier on the quotation PDF"
```

---

### Task 7: README with screenshots

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: nothing (this is documentation).
- Produces: `README.md` at the repo root.

- [ ] **Step 1: Take the two screenshots**

With the stack running and a tier configured (Task 2's manual verification) and a quotation with a tier-triggered discount and margin guard banner (Task 5's manual verification):
1. Screenshot the Sales → Configuration → Pricing Tiers list. Save as `docs/screenshots/pricing-tiers.png`.
2. Screenshot (or export) the generated quotation PDF from Task 6's verification, showing the "Volume discount applied" note. Save as `docs/screenshots/quotation-pdf.png`.

- [ ] **Step 2: Get the exact test count**

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all 2>&1 | grep -i "tests\|failures"
```
Use the passing count from this output as `<N>` below.

- [ ] **Step 3: Write the README**

`README.md`:

```markdown
# sale_tiered_pricing

**<N> passing tests.** An Odoo 19 addon that applies volume discount tiers to
quotation lines automatically, flags quotations whose aggregate margin falls
below a configurable minimum, and extends the quotation PDF to show the
applied tier.

## What it does

- **Volume discount tiers** (`sale.pricing.tier`): a global, ordered ladder
  of quantity thresholds and discount percentages. Sales, Configuration,
  Pricing Tiers.
- **Automatic discounting**: each quotation line's quantity is matched
  against the tier ladder and the discount is applied to Odoo's native
  `discount` field — no parallel pricing mechanism.
- **Margin guard**: a configurable minimum margin percentage (Settings,
  Sales) is checked against the quotation's aggregate margin, computed by
  Odoo's own `sale_margin` module. Quotations below the minimum show a
  warning banner. The guard flags — it never blocks saving.
- **Quotation PDF**: shows which tier was applied per line.

![Pricing tier configuration](docs/screenshots/pricing-tiers.png)
![Generated quotation PDF](docs/screenshots/quotation-pdf.png)

## Design decision: why tiers live on their own model

Volume discounts are usually negotiated at the company level — "10 or more
gets 5% off" — not configured per product. Putting tiers on their own model
(`sale.pricing.tier`) instead of as fields on `product.template` keeps the
discount ladder in one place, editable without touching every product, and
keeps `sale.order.line`'s job limited to *matching* a tier rather than
*defining* one.

## Running it

```bash
docker compose up -d
docker compose exec odoo odoo -d sale_tiered_pricing -i sale_tiered_pricing --without-demo=all
```

Then open `http://localhost:8069`.

## Running the tests

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all
```

## Scope

Deliberately out of scope: multi-currency tier thresholds, per-product or
per-category tier scoping (tiers are global), and blocking save when the
margin guard triggers.
```

- [ ] **Step 4: Commit**

```bash
git add README.md docs/screenshots/
git commit -m "docs: add README with screenshots and design rationale"
```

---

## Not part of this plan

The portfolio site integration (adding an entry to `portfolio/src/lib/projects.ts` and images to `portfolio/public/projects/`) is a separate, later bounded task in the `portfolio` repo — it needs this repo's final GitHub URL and the screenshots from Task 7, neither of which exist until this plan is done.
