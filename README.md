# sale_tiered_pricing

**18 passing tests.** An Odoo 19 addon that applies volume discount tiers to
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
docker compose exec odoo odoo -d sale_tiered_pricing -i sale_tiered_pricing --without-demo=all --db_host=db --db_user=odoo --db_password=odoo --stop-after-init
```

Then open `http://localhost:8069`.

## Running the tests

```bash
docker compose exec odoo odoo -d sale_tiered_pricing_test -i sale_tiered_pricing --test-enable --stop-after-init --without-demo=all --db_host=db --db_user=odoo --db_password=odoo
```

## Scope

Deliberately out of scope: multi-currency tier thresholds, per-product or
per-category tier scoping (tiers are global), and blocking save when the
margin guard triggers.
