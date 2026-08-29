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
