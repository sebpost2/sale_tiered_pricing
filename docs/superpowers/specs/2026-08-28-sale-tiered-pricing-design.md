# sale_tiered_pricing — Odoo module design

**Date:** 2026-08-28
**Status:** Approved for planning

## Goal

Build a real, installable Odoo 19 addon — `sale_tiered_pricing` — as a portfolio
piece demonstrating genuine Odoo technical development: a new model, core-model
inheritance, computed fields with correct dependencies, proper access rights,
a QWeb report, and a real automated test suite. This is the primary Odoo
evidence in the candidate's portfolio; it must install cleanly on a stock Odoo
instance with zero external dependencies (no API keys, no network calls, no
mocking).

## Why this module

- Domain the candidate already knows cold (built a CPQ with nine proposal
  templates at Inbrasol) — this is re-expressing known business logic as
  original code, not learning a new problem.
- Exercises the four things an Odoo technical lead actually checks: new
  model, `sale.order.line` inheritance, computed fields, `ir.model.access.csv`
  done correctly.
- The test suite is the differentiator — most custom Odoo modules on GitHub
  ship no meaningful test coverage.

## Scope

**In scope:**
- Volume discount tiers applied automatically to quotation lines by quantity.
- A margin guard flagging quotes whose aggregate margin falls below a
  configurable minimum.
- A QWeb quotation report showing the applied discount.
- 15-25 TransactionCase tests covering the boundary matrix below.
- A README with screenshots and a design-decision paragraph.

**Out of scope (explicit):**
- Multi-currency tier thresholds.
- Per-product-category or per-product tier scoping (tiers are global).
- Blocking save when the margin guard triggers — it flags, it doesn't block.
- The portfolio site integration (`portfolio/src/lib/projects.ts`) — a
  separate, later bounded task once this repo, its screenshots, and its
  GitHub URL exist.
- AI/LLM bridge features (explicitly deferred to a future follow-up project).

## Environment & repo layout

Runs via Docker Compose — `odoo:19` + `postgres:16` — so anyone cloning the
repo can install the module against a stock Odoo with `docker compose up`.
No native Postgres or Odoo install required on the dev machine.

```
sale_tiered_pricing/
  docker-compose.yml
  addons/sale_tiered_pricing/
    __manifest__.py          # depends: sale, sale_margin
    models/
      pricing_tier.py         # sale.pricing.tier
      sale_order.py            # sale.order inherit — aggregate margin guard
      sale_order_line.py       # sale.order.line inherit — tier match, discount
    views/
      pricing_tier_views.xml
      sale_order_views.xml     # margin-guard banner on the quotation form
    report/
      quotation_report.xml     # QWeb, extends native quotation template
    security/
      ir.model.access.csv
    tests/
      test_pricing_tier.py
  README.md
```

Repo: new local git repo at `D:\2_MyScripts\FINANCE\sale_tiered_pricing`
(sibling to `portfolio`, `job-alert-agent`, etc.). GitHub remote created later,
during implementation — not part of this design step.

## Data model

### `sale.pricing.tier` (new model)

Standalone model, not fields on `product.template` — a global, ordered ladder
of discount tiers rather than per-product configuration. This keeps the model
and the test matrix simple, and matches how volume pricing is usually
negotiated at the company level rather than per-SKU. (This is the design
decision the README's "why tiers live on their own model" paragraph explains.)

| Field              | Type    | Notes                                   |
|---------------------|---------|------------------------------------------|
| `name`              | Char    | e.g. "10+ units"                          |
| `min_qty`            | Float   | Quantity threshold                        |
| `discount_percent`  | Float   | Percentage discount applied               |
| `sequence`          | Integer | Display ordering                          |

Tier matching: the applicable tier for a given quantity is the one with the
highest `min_qty` that is `<= product_uom_qty`. No matching tier → zero
discount. This is where "overlapping tiers → highest wins" is decided.

### `sale.order.line` (inherited)

- `tier_id` (Many2one to `sale.pricing.tier`, computed, stored) — the
  best-matching tier for the line's current quantity.
- The line's **native** `discount` field is set from the matched tier's
  `discount_percent` (computed) — reusing Odoo's existing discount mechanism
  instead of inventing a parallel price/discount field.
- Recomputes on `product_uom_qty` change (`@api.depends`).

### `sale.order` (inherited)

Depends on core `sale_margin` (ships with stock Odoo — no external
dependency), which already computes `margin` / `margin_percent` per line from
product cost vs. price. This module does not reimplement margin math.

- `margin_guard_min_percent` — configurable minimum margin, company-scoped,
  exposed via `res.config.settings`.
- `margin_guard_triggered` (Boolean, computed) — true when the order's
  aggregate margin percent (sum of line margins / sum of line subtotals)
  falls below `margin_guard_min_percent`.
- `margin_guard_message` (Char, computed) — human-readable reason, shown as a
  banner on the quotation form.

The guard is aggregate/order-level by design: a single bad line can otherwise
hide inside an order whose total looks healthy. This is also what gives the
"multi-line orders aggregate correctly" test real meaning.

## Security & views

- `ir.model.access.csv`: read access to `sale.pricing.tier` for the base
  Sales user group, write access for Sales Manager.
- Tier configuration: a simple list/form view under Sales → Configuration.
- Quotation form: inherited view adding the margin-guard banner — no
  full view rebuild.

## QWeb report

Inherits/extends the native `sale.report_saleorder_document` template rather
than replacing it. The applied discount is already visible via the native
`discount` column; the extension adds a small note naming the matched tier.

## Test suite (TransactionCase, ~15-25 tests)

- Quantity exactly at a tier minimum, one below, one above.
- No matching tier → zero discount.
- Overlapping tiers → highest applicable wins.
- Discount recomputes when quantity changes.
- Margin correct with and without discount applied.
- Below-threshold aggregate margin triggers the guard; above-threshold does not.
- Multi-line orders: guard reflects the aggregate, not any single line.
- Rounding at currency precision (via `currency_id.round()`).

## README

Written on Day 2. Contents, in order:
1. Test count at the top.
2. Screenshot of tier configuration.
3. Screenshot of the generated quotation PDF.
4. One paragraph on the standalone-model design decision (see Data model
   section above).
5. Note on out-of-scope items (category scoping, multi-currency) as
   documented future extensions.

## Timeline

- **Day 1:** Docker Compose environment, models, computed fields, security,
  minimal views. Module installs cleanly on a fresh Odoo instance.
- **Day 2:** QWeb report, full test suite, README with screenshots.

## Follow-on (not part of this spec)

Once the module, its tests, and its screenshots exist: add a one-line
portfolio entry to `portfolio/src/lib/projects.ts` (EN/ES, matching the
existing project-card format) and push project images to
`portfolio/public/projects/`. That is a separate bounded task in the
`portfolio` repo.
