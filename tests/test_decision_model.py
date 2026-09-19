import unittest
from elemzes.decision_model import Costs, scenario, assessment
from porcelan.parsing import extract_availability
from bs4 import BeautifulSoup
import json
from elemzes.candidate_filter import screening_reason


class DecisionTests(unittest.TestCase):
    def test_model_names_do_not_turn_parts_into_products(self):
        examples = [("Biostar alaplap FM2", "Nikon FM2"),
                    ("Canon AE-1 markolat", "Canon AE-1"),
                    ("Amiga 500 memória bővítő", "Amiga 500"),
                    ("Olympus MJU II nem kapcsol be", "Olympus mju II"),
                    ("Flektogon 20mm f4", "Flektogon 35")]
        for title, model in examples:
            self.assertIsNotNone(screening_reason(title, model))
        self.assertIsNone(screening_reason("SEGA MASTER SYSTEM II konzol", "Sega Master System"))

    def test_shipping_and_risk_can_reverse_apparent_profit(self):
        result = scenario(8000, 20000)
        self.assertLess(result["profit_huf"], 0)

    def test_bid_ceiling_satisfies_target_after_all_costs(self):
        c = Costs()
        ceiling = scenario(10000, 60000, c)["max_purchase_huf"]
        self.assertGreaterEqual(scenario(ceiling, 60000, c)["roi_pct"], 30)

    def test_active_comps_never_prove_liquidity(self):
        good = {"profit_huf": 50000, "roi_pct": 90}
        self.assertIn("nem igazolt", assessment("in_stock", "fix", 100, good, good))
        self.assertEqual(assessment("unavailable", "fix", 100, good, good),
                         "Elérhetőség nem igazolt")

    def test_reject_invalid_costs(self):
        for value in (-1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                Costs(outbound=value)


class AvailabilityTests(unittest.TestCase):
    def page(self, state, sku=123456, end=None):
        offer = {"availability": "https://schema.org/" + state}
        if end:
            offer["availabilityEnds"] = end
        data = {"@type": "Product", "sku": sku, "offers": offer}
        return BeautifulSoup('<script type="application/ld+json">' + json.dumps(data)
                             + '</script><div class="tw-hidden">A termék elkelt fix áron.</div>',
                             "html.parser")

    def test_hidden_sold_template_is_not_a_sale(self):
        self.assertEqual(extract_availability(self.page("InStock"),
                         "https://www.vatera.hu/item-123456.html"), "in_stock")

    def test_sold_and_expired_offers_are_unavailable(self):
        url = "https://www.vatera.hu/item-123456.html"
        self.assertEqual(extract_availability(self.page("SoldOut"), url), "unavailable")
        self.assertEqual(extract_availability(self.page("InStock", end="2000-01-01T00:00:00Z"), url),
                         "unavailable")

    def test_other_products_do_not_establish_availability(self):
        self.assertEqual(extract_availability(self.page("InStock", sku=999999),
                         "https://www.vatera.hu/item-123456.html"), "unverified")
