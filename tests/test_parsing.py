"""Parser tesztek a tests/fixtures HTML-eken."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from porcelan import config, parsing, vatera  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
BASE = "https://www.vatera.hu"


def load(name: str) -> tuple[str, str]:
    return f"{BASE}/{name}", (FIX / name).read_text(encoding="utf-8")


class SaleTypeTest(unittest.TestCase):
    def test_auction(self):
        rec = parsing.parse_listing(*load("herendi-apponyi-vaza-100000001.html"))
        self.assertEqual(rec["sale_type"], config.SALE_AUCTION)
        self.assertEqual(rec["current_bid_huf"], 18000)
        self.assertEqual(rec["start_bid_huf"], 9900)
        self.assertEqual(rec["price_huf"], 18000)
        self.assertEqual(rec["bid_count"], 3)
        self.assertEqual(rec["end_time"], "2026. 03. 20. 20:00")

    def test_fix(self):
        rec = parsing.parse_listing(*load("zsolnay-eozin-keszlet-100000002.html"))
        self.assertEqual(rec["sale_type"], config.SALE_FIX)
        self.assertEqual(rec["price_huf"], 24900)          # nem a szállítási díj
        self.assertFalse(rec["offer_possible"])

    def test_offer(self):
        rec = parsing.parse_listing(*load("herendi-rothschild-keszlet-100000003.html"))
        self.assertEqual(rec["sale_type"], config.SALE_OFFER)
        self.assertTrue(rec["offer_possible"])
        self.assertEqual(rec["price_huf"], 890000)

    def test_live_gtm_marker_wins_over_page_boilerplate(self):
        """Élő oldal: minden oldalon ott a 'Licitáljon most' és az 'Irányár:' szöveg."""
        boilerplate = ("<p>Licitáljon most - ez a tárgy Önre vár!</p>"
                       "<p>Fix ár: 16 800 Ft Irányár: 16 800 Ft</p>")
        text = parsing.norm(boilerplate)

        def page(kind: str, bestoffer: str) -> str:
            return (f'<span class="gtm-auction-type tw-hidden">{kind}</span>{boilerplate}'
                    f'<script>var p = {{"product_bestofferminpercent":{bestoffer}}};</script>')

        self.assertEqual(parsing.detect_sale_type(page("fix_price", "null"), text),
                         (config.SALE_FIX, False))
        self.assertEqual(parsing.detect_sale_type(page("fix_price", "80"), text),
                         (config.SALE_OFFER, True))
        self.assertEqual(parsing.detect_sale_type(page("bid", "null"), text),
                         (config.SALE_AUCTION, False))


class RelevanceTest(unittest.TestCase):
    def test_brands(self):
        herend = parsing.parse_listing(*load("herendi-apponyi-vaza-100000001.html"))
        zsolnay = parsing.parse_listing(*load("zsolnay-eozin-keszlet-100000002.html"))
        self.assertEqual(herend["brand"], config.BRAND_HEREND)
        self.assertEqual(zsolnay["brand"], config.BRAND_ZSOLNAY)
        self.assertTrue(herend["accepted"] and zsolnay["accepted"])

    def test_fake_rejected(self):
        rec = parsing.parse_listing(*load("herendi-stilusu-figura-100000004.html"))
        self.assertFalse(rec["accepted"])
        self.assertIn("utanzat", rec["reject_reason"])

    def test_non_porcelain_rejected(self):
        rec = parsing.parse_listing(*load("zsolnay-konyv-100000005.html"))
        self.assertFalse(rec["accepted"])
        self.assertIn("nem porcelan", rec["reject_reason"])

    def test_mintas_only_flagged(self):
        """'Rothschild mintás' valódi tétel – csak gyanú jelzés, nem kizárás."""
        rec = parsing.parse_listing(*load("herendi-rothschild-keszlet-100000003.html"))
        self.assertTrue(rec["accepted"])
        self.assertIn("mintas", rec["suspect_flags"])

    def test_damage_and_decor(self):
        rec = parsing.parse_listing(*load("zsolnay-eozin-keszlet-100000002.html"))
        self.assertIn("csorba", rec["damage_flags"])
        self.assertIn("eozin", rec["decor_hints"])


class LikvidProfileTest(unittest.TestCase):
    KEYS = ["PROFILE", "SEARCH_TERMS", "BRAND_TOKENS", "FAKE_CUES", "NON_PORCELAIN_CUES",
            "BRAND_IN_TITLE_ONLY", "NO_BRAND_LABEL", "FAKE_LABEL", "NON_ITEM_LABEL"]

    def setUp(self):
        self.saved = {k: getattr(config, k) for k in self.KEYS}
        config.apply_profile("likvid")

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(config, k, v)

    def accepted(self, title: str) -> bool:
        return parsing.relevance(title, parsing.norm(title))["accepted"]

    def test_accepts_target_items(self):
        for title in ("Helios 44-2 58mm f2 objektív M42",
                      "Poljot chronograph 3133 karóra szíjjal",
                      "Tungsram EL34 elektroncső pár",
                      "Zenit E fényképezőgép"):
            self.assertTrue(self.accepted(title), title)

    def test_rejects_parts_and_accessories(self):
        for title in ("Helios 44 adapter M42-Sony", "Jupiter 9 objektív gombás lencse",
                      "Poljot óraszíj", "Herendi porcelán váza"):
            self.assertFalse(self.accepted(title), title)

    def test_brand_only_in_page_text_is_not_enough(self):
        rel = parsing.relevance("Régi fényképezőgép", parsing.norm("ajánlott: helios 44"))
        self.assertFalse(rel["accepted"])


class HelperTest(unittest.TestCase):
    def test_listing_id(self):
        self.assertEqual(parsing.listing_id(f"{BASE}/herendi-vaza-123456789.html"),
                         "123456789")
        self.assertIsNone(parsing.listing_id(f"{BASE}/sugo.html"))

    def test_shipping_not_taken_as_price(self):
        text = parsing.norm("Fix ár: 12 500 Ft Szállítás ára: 1 590 Ft")
        self.assertEqual(parsing.amount_after(text, ["fix ar", "ara"]), 12500)

    def test_product_links_only(self):
        html = (FIX / "search.html").read_text(encoding="utf-8")
        links = vatera.extract_product_links(html)
        self.assertEqual(len(links), 5)
        self.assertTrue(all(link.endswith(".html") for link in links))
        self.assertNotIn(f"{BASE}/sugo.html", links)

    def test_product_links_dedup_fragment(self):
        html = (f'<a href="{BASE}/herendi-vaza-3527373158.html">x</a>'
                f'<a href="{BASE}/herendi-vaza-3527373158.html#bidlink">licit</a>')
        self.assertEqual(vatera.extract_product_links(html),
                         [f"{BASE}/herendi-vaza-3527373158.html"])

    def test_split_by_sale_type(self):
        records = [parsing.parse_listing(*load(n)) for n in (
            "herendi-apponyi-vaza-100000001.html",
            "zsolnay-eozin-keszlet-100000002.html",
            "herendi-rothschild-keszlet-100000003.html",
        )]
        buckets = vatera.split_by_sale_type(records)
        self.assertEqual([len(buckets[t]) for t in config.SALE_TYPES], [1, 1, 1])


if __name__ == "__main__":
    unittest.main()
