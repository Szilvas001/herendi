"""A több forrású gyűjtés szabályai (hálózat és PostgreSQL nélkül).

A lényeg, amit rögzítünk: egy adatpont csak akkor érvényes, ha legalább három
képe, érdemi leírása és ára van; a sitemapből a márkás tétel-URL-ek szűrődnek
ki; a schema.org Product blokkból a képek, a leírás és az ár helyesen jön.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IsolatedEnv  # noqa: E402

CFG = {
    "market": "HU",
    "sitemap_url": "https://pelda.hu/sitemap/sitemap.xml",
    "item_url_pattern": "/termekek/reszletek/",
    "slug_patterns": ["herend", "zsolnay", "eozin"],
}

SITEMAP_INDEX = """<?xml version='1.0'?><sitemapindex>
<sitemap><loc>https://pelda.hu/sitemap/products_01.xml</loc></sitemap>
<sitemap><loc>https://pelda.hu/sitemap/categories.xml</loc></sitemap>
</sitemapindex>"""

TERMEK_SITEMAP = """<?xml version='1.0'?><urlset>
<url><loc>https://pelda.hu/termekek/reszletek/porcelan/1/Herendi-Apponyi-vaza/</loc></url>
<url><loc>https://pelda.hu/termekek/reszletek/porcelan/2/Zsolnay-eozin-kaspo/</loc></url>
<url><loc>https://pelda.hu/termekek/reszletek/butor/3/Tolgyfa-komod/</loc></url>
<url><loc>https://pelda.hu/rolunk/</loc></url>
</urlset>"""


def termekoldal(kepszam: int, leiras: str = "Kézzel festett Herendi váza, 24 cm magas, hibátlan.",
                ar: str = "42600", elerheto: str = "InStock") -> str:
    kepek = ", ".join(f'"https://kep.pelda.hu/{i}.jpg"' for i in range(kepszam))
    return f"""<html><head>
    <script type="application/ld+json">
    {{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
      {{"@type":"ListItem","position":1,"item":{{"name":"Porcelán"}}}},
      {{"@type":"ListItem","position":2,"item":{{"name":"Herendi"}}}}]}}
    </script>
    <script type="application/ld+json">
    {{"@context":"https://schema.org","@type":"Product","sku":"1",
     "name":"Herendi Apponyi váza 24 cm",
     "description":"<p>{leiras}</p>",
     "image":[{kepek}],
     "offers":{{"@type":"Offer","priceCurrency":"HUF","price":"{ar}",
                "availability":"https://schema.org/{elerheto}"}}}}
    </script></head><body>tartalom</body></html>"""


class SchemaOrgForrasTest(unittest.TestCase):
    def forras(self):
        from porcelan.sources.schemaorg import SchemaOrgForras
        return SchemaOrgForras("pelda", CFG)

    def test_sitemap_szures_markara(self):
        with IsolatedEnv():
            f = self.forras()
            alsitemapek, tetelek = f.sitemap_alatt(CFG["sitemap_url"], SITEMAP_INDEX)
            self.assertEqual(len(alsitemapek), 2)
            self.assertEqual(tetelek, [])

            _, tetelek = f.sitemap_alatt("https://pelda.hu/sitemap/products_01.xml", TERMEK_SITEMAP)
            self.assertEqual(len(tetelek), 2)          # a komód és a rólunk oldal kimarad
            self.assertTrue(all("herend" in u.lower() or "zsolnay" in u.lower() for u in tetelek))

    def test_termekoldal_kinyerese(self):
        with IsolatedEnv():
            adat = self.forras().adatpont("https://pelda.hu/termekek/reszletek/porcelan/1/x/",
                                          termekoldal(5))
            self.assertEqual(adat["source"], "pelda")
            self.assertEqual(adat["source_id"], "1")
            self.assertEqual(adat["price_huf"], 42600)
            self.assertEqual(adat["currency"], "HUF")
            self.assertEqual(len(adat["images"]), 5)
            self.assertEqual(adat["brand"], "Herendi")
            self.assertEqual(adat["size_cm"], 24.0)
            self.assertIn("Kézzel festett", adat["description"])
            self.assertNotIn("<p>", adat["description"])     # a HTML ki van szedve
            self.assertEqual(adat["category"], "Porcelán > Herendi")
            self.assertEqual(adat["price_type"], "asking_active")

    def test_elkelt_tetel_realizalt_arkent(self):
        with IsolatedEnv():
            adat = self.forras().adatpont("https://pelda.hu/termekek/reszletek/porcelan/1/x/",
                                          termekoldal(4, elerheto="SoldOut"))
            self.assertEqual(adat["price_type"], "realized_sale")

    def test_schema_nelkuli_oldal(self):
        with IsolatedEnv():
            self.assertIsNone(self.forras().adatpont("https://pelda.hu/x/", "<html>semmi</html>"))


class FelveteliFeltetelTest(unittest.TestCase):
    """A három kép / leírás / ár feltétel – ez a korpusz minőségi kapuja."""

    def ellenoriz(self, **modosit):
        from porcelan import pg
        adat = {"title": "Herendi váza", "description": "Kézzel festett darab, hibátlan állapotban.",
                "price_huf": 42600, "images": [{"url": f"{i}.jpg"} for i in range(3)]}
        adat.update(modosit)
        return pg.ervenyes(adat)

    def test_harom_kep_kell(self):
        self.assertIsNone(self.ellenoriz())
        self.assertIn("2 kép", self.ellenoriz(images=[{"url": "a"}, {"url": "b"}]))
        self.assertIn("0 kép", self.ellenoriz(images=[]))

    def test_leiras_es_ar_kell(self):
        self.assertEqual(self.ellenoriz(description="rövid"), "nincs érdemi leírás")
        self.assertEqual(self.ellenoriz(price_huf=None), "nincs ár")
        self.assertEqual(self.ellenoriz(price_huf=0), "nincs ár")
        self.assertEqual(self.ellenoriz(title=""), "nincs cím")


class ParticioNevTest(unittest.TestCase):
    def test_forrasnev_ellenorzese(self):
        from porcelan import pg
        self.assertEqual(pg._particio_nev("galeriasavaria"), "galeriasavaria")
        self.assertEqual(pg._particio_nev("Gal-Sav.hu"), "gal_sav_hu")
        with self.assertRaises(ValueError):
            pg._particio_nev("")


if __name__ == "__main__":
    unittest.main()
