"""Sitemap-alapú felderítés a Vaterán (hálózat nélkül).

A Vatera robots.txt-je tiltja a /listings/ keresőkontrollert, de meghirdeti a
sitemapet, és engedi a kategória- (index-cNNN.html) és termékoldalakat. Ez a
teszt azt rögzíti, hogy a felderítés ezen a megengedett úton megy:

1. a sitemap-index alól az al-sitemapok bejárási feladatként jelennek meg,
2. a tétel-sitemapból a márkás hirdetések a slug alapján, termékoldal letöltése
   nélkül kiszűrődnek,
3. a kategóriaoldal lapozása a "N. oldal / M összesen" jelzésből folytatódik,
4. a keresőoldalak alapból nem kerülnek be a feladatok közé.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IsolatedEnv  # noqa: E402

SITEMAP_INDEX = """<?xml version='1.0' encoding='UTF-8'?>
<sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
  <sitemap><loc>https://www.vatera.hu/sitemap/sitemap-categories.xml</loc></sitemap>
  <sitemap><loc>https://www.vatera.hu/sitemap_1_17.xml.gz</loc></sitemap>
</sitemapindex>"""

ITEM_SITEMAP = """<?xml version='1.0' encoding='UTF-8'?>
<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
  <url><loc>https://www.vatera.hu/herendi-apponyi-vaza-100000001.html</loc></url>
  <url><loc>https://www.vatera.hu/zsolnay-eozin-keszlet-100000002.html</loc></url>
  <url><loc>https://www.vatera.hu/kerti-locsolotomlo-100000009.html</loc></url>
  <url><loc>https://www.vatera.hu/sugo/adatvedelem.html</loc></url>
</urlset>"""

CATEGORY_HTML = """<html><body>
  <div class="breadcrumb">Porcelánok (14707 db)</div>
  <div class="pages">1. oldal / 295 összesen</div>
  <span class="listing-pager-actual-page">1</span>
  <div class="pagination">
    <span class="page-number active">1</span><a class="page-number" href="?p=2">2</a>
  </div>
  <div data-product-id="100000001" data-gtm-name="Herendi Apponyi váza"
       data-gtm-price="18000" data-gtm-currency="HUF" data-gtm-auction-type="fix_price">
    <a class="product_link" href="/herendi-apponyi-vaza-100000001.html">Herendi Apponyi váza</a>
  </div>
</body></html>"""

LAST_PAGE_HTML = CATEGORY_HTML.replace("1. oldal / 295 összesen", "295. oldal / 295 összesen")


class SitemapDiscoveryTest(unittest.TestCase):
    def source(self):
        from porcelan.sources.vatera import VateraSource
        return VateraSource()

    def test_seed_tasks_avoid_disallowed_search(self):
        with IsolatedEnv():
            tasks = self.source().seed_tasks()
            kinds = {t.kind for t in tasks}
            self.assertIn("sitemap", kinds)
            self.assertIn("category", kinds)
            # a robots.txt által tiltott keresőkontroller nem kerül a feladatok közé
            self.assertNotIn("search", kinds)
            self.assertFalse([t for t in tasks if "/listings/" in t.url])

    def test_sitemap_index_yields_subsitemaps(self):
        with IsolatedEnv():
            src = self.source()
            page = src.parse_index("https://www.vatera.hu/sitemap/sitemap.xml", SITEMAP_INDEX)
            self.assertEqual(page.cards, [])
            self.assertEqual(len(page.categories), 2)
            self.assertTrue(all(src.is_relevant_category(u) for u in page.categories))
            self.assertIs(page.has_next, False)      # a sitemapon nincs lapozás

    def test_item_sitemap_filters_brands_by_slug(self):
        with IsolatedEnv():
            page = self.source().parse_index("https://www.vatera.hu/sitemap_1_17.xml.gz", ITEM_SITEMAP)
            ids = {c.source_id for c in page.cards}
            self.assertEqual(ids, {"100000001", "100000002"})    # a locsolótömlő és a súgóoldal kimarad
            titles = {c.source_id: c.title for c in page.cards}
            self.assertIn("herendi", titles["100000001"])
            self.assertIn("zsolnay", titles["100000002"])

    def test_category_pagination_and_total(self):
        with IsolatedEnv():
            src = self.source()
            url = "https://www.vatera.hu/antik-regiseg/porcelanok/index-c212.html"
            page = src.parse_index(url, CATEGORY_HTML)
            self.assertEqual(len(page.cards), 1)
            self.assertEqual(page.reported_total, 14707)
            self.assertIs(page.has_next, True)
            self.assertEqual(page.cards[0].price_huf, 18000)
            last = src.parse_index(url, LAST_PAGE_HTML)
            self.assertIs(last.has_next, False)      # az utolsó oldalon megáll a lapozás

    def test_gzip_body_is_decompressed_as_text(self):
        import gzip
        from porcelan.net import Fetcher
        self.assertEqual(Fetcher._maybe_gunzip(gzip.compress(ITEM_SITEMAP.encode())).decode(),
                         ITEM_SITEMAP)
        self.assertEqual(Fetcher._maybe_gunzip(b"<urlset/>"), b"<urlset/>")


if __name__ == "__main__":
    unittest.main()
