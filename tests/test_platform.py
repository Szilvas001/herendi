"""A termék kritikus részeinek tesztjei (hálózat nélkül).

Lapozás és lefedettség, duplikáció- és újrahirdetés-szűrés, ár- és pénznemkezelés,
aukciók elkülönítése, CSV-import, modellbetöltés, nyereségszámítás, dashboard-szűrés.
"""
import csv
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import FIX, IsolatedEnv, synthetic_price_records

CRAWL = FIX / "crawl"


def _crawl(conn, **kw):
    from porcelan.crawler import Crawler
    from porcelan.net import Fetcher
    return Crawler("vatera", conn, fetcher=Fetcher(offline_dir=CRAWL, min_delay=0), **kw).run()


class CrawlTest(unittest.TestCase):
    def test_pagination_coverage_status_and_incremental(self):
        with IsolatedEnv(CRAWL / "settings.toml"):
            from porcelan import db
            conn = db.get_conn()
            res = _crawl(conn)
            self.assertEqual(res["status"], "completed")
            st = res["stats"]
            self.assertEqual(st["index_pages"], 2)          # mindkét találati oldal, a lapozás végéig
            self.assertEqual(st["cards"], 5)
            scope = [s for s in res["coverage"]["detail"] if s["scope"] == "query:herendi"][0]
            self.assertTrue(scope["exhausted"])
            self.assertEqual(scope["reported_total"], 5)
            self.assertEqual(scope["seen"], 5)
            # a nem letölthető kategóriaoldal miatt a futás NEM teljes – és nem is állítjuk annak
            self.assertFalse(res["coverage"]["complete"])
            rows = {r["source_id"]: r for r in conn.execute("SELECT * FROM listings")}
            self.assertEqual(rows["300000003"]["relevance"], "rejected")        # "stílusú"
            self.assertIsNone(rows["300000003"]["last_checked"])                # nem töltöttük le
            self.assertEqual(rows["300000001"]["sale_type"], "fix")
            self.assertEqual(rows["300000002"]["sale_type"], "aukcio")
            self.assertEqual(rows["300000002"]["current_bid_huf"], 9000)
            self.assertEqual(rows["300000002"]["condition"], "serult")          # "csorba"
            self.assertEqual(rows["300000005"]["status"], "sold")               # licittel lezárult aukció
            pr = {(r["source_ref"], r["price_type"]): r for r in
                  conn.execute("SELECT source_ref, price_type, amount, corpus, description FROM price_records")}
            self.assertEqual(pr[("300000005", "auction_final_bid")]["amount"], 5000.0)   # záró licit
            self.assertEqual(pr[("300000001", "asking_active")]["amount"], 18000.0)      # fix ár = kínálati ár
            self.assertIn("pajzspecs", pr[("300000001", "asking_active")]["description"])  # részletes oldalból
            self.assertEqual(pr[("300000001", "asking_active")]["corpus"], "herend_zsolnay")
            # futó aukció licitje és az utánzat nem kerül tanítóadatba
            self.assertNotIn(("300000002", "asking_active"), pr)
            self.assertNotIn(("300000003", "asking_active"), pr)
            self.assertGreater(conn.execute("SELECT COUNT(*) FROM images").fetchone()[0], 4)
            # második futás: nincs új hirdetés, a friss részletes oldalakat nem tölti le újra
            res2 = _crawl(conn)
            self.assertEqual(res2["stats"]["new"], 0)
            self.assertEqual(res2["stats"]["detail_pages"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0], 5)
            # az elkelt státuszt a lejártat jelző kártya nem írja vissza "ended"-re
            self.assertEqual(conn.execute("SELECT status FROM listings WHERE source_id='300000005'").fetchone()[0], "sold")

    def test_resume_after_interruption(self):
        with IsolatedEnv(CRAWL / "settings.toml"):
            from porcelan import db
            conn = db.get_conn()
            r1 = _crawl(conn, max_requests=2)
            self.assertEqual(r1["status"], "interrupted")
            r2 = _crawl(conn)
            self.assertEqual(r2["run_id"], r1["run_id"])       # ugyanazt a bejárást folytatta
            self.assertEqual(r2["status"], "completed")
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0], 5)

    def test_blocked_source_stops_without_bypass(self):
        import tempfile
        from pathlib import Path
        from porcelan import db
        from porcelan.crawler import Crawler
        from porcelan.net import Fetcher
        with IsolatedEnv(CRAWL / "settings.toml"):
            d = Path(tempfile.mkdtemp())
            (d / "urls.txt").write_text("https://www.vatera.hu/listings/index.php?q=herendi\tcaptcha.html\n")
            (d / "captcha.html").write_text("<html><div class='g-recaptcha'></div></html>")

            class BlockingFetcher(Fetcher):
                def get(self, url, ttl=0, binary=False):
                    resp = super().get(url, ttl, binary)
                    marker = self.block_marker(resp.text if resp else "")
                    if marker:
                        from porcelan.net import BlockedError
                        raise BlockedError(marker)
                    return resp
            res = Crawler("vatera", db.get_conn(), fetcher=BlockingFetcher(offline_dir=d, min_delay=0)).run()
            self.assertEqual(res["status"], "blocked")


class ParsingTest(unittest.TestCase):
    def test_price_and_currency(self):
        from porcelan.sources.base import parse_hu_datetime, to_int_huf
        self.assertEqual(to_int_huf("12 900 Ft"), 12900)
        self.assertEqual(to_int_huf("1.250.000 Ft"), 1250000)
        self.assertEqual(to_int_huf("24 990,50 Ft"), 24990)
        self.assertIsNone(to_int_huf("ingyenes"))
        self.assertEqual(parse_hu_datetime("2026.10.03. 19:11"), "2026-10-03T17:11:00+00:00")  # CEST → UTC
        self.assertEqual(parse_hu_datetime("2026.12.03. 19:11"), "2026-12-03T18:11:00+00:00")  # CET → UTC

    def test_card_with_foreign_currency_has_no_huf_price(self):
        with IsolatedEnv():
            from porcelan.sources.vatera import VateraSource
            html = ('<div data-product-id="123456789" data-gtm-name="Herendi váza" data-gtm-price="100" '
                    'data-gtm-currency="EUR" data-gtm-auction-type="fix_price" data-expired="0">'
                    '<a class="product_link" href="/herendi-vaza-123456789.html">x</a></div>')
            page = VateraSource().parse_index("https://www.vatera.hu/listings/index.php?q=x", html)
            self.assertEqual(len(page.cards), 1)
            self.assertIsNone(page.cards[0].price_huf)

    def test_feature_extraction(self):
        from porcelan import text
        f = text.extract("Herendi Apponyi zöld váza, kézzel festett, pajzspecséttel jelzett, 24 cm")
        self.assertEqual((f["brand"], f["object_type"], f["decor"], f["size_cm"]), ("Herendi", "vase", "Apponyi", 24.0))
        self.assertIn("marked", f["mark_flags"])
        self.assertEqual(text.extract("Zsolnai teáskészlet 15 db hibátlan")["pieces"], 15)
        self.assertEqual(text.extract("Zsolnay váza, nincs rajta sérülés")["condition"], "ismeretlen")
        self.assertEqual(text.extract("Zsolnay váza, hibátlan")["condition"], "hibatlan")
        self.assertEqual(text.extract("Herendi figura ragasztott fül")["condition"], "javitott")
        self.assertEqual(text.relevance("Herendi stílusú váza", text.extract("Herendi stílusú váza"))[0], "rejected")
        self.assertEqual(text.relevance("Kézzel festett porcelán madár",
                                        text.extract("Kézzel festett porcelán madár"))[0], "visual_candidate")
        self.assertEqual(text.dedup_key("Herendi váza 24 cm", seller="a"), text.dedup_key("herendi  VÁZA 25 cm", seller="a"))


class ImportTest(unittest.TestCase):
    def _legacy_csv(self, path):
        from porcelan import storage
        rows = [
            {"listing_id": "3491251307", "brand": "Herendi", "title": "Herendi Rothschild 6 sz étkészlet",
             "sale_type": "fix", "price_huf": "899000", "url": "https://www.vatera.hu/x-3491251307.html",
             "accepted": "True", "description": "Hibátlan állapotú"},
            {"listing_id": "3528306179", "brand": "Herendi", "title": "Herendi női akt",
             "sale_type": "aukcio", "price_huf": "120000", "start_bid_huf": "120000", "price_kind": "kikialtasi ar",
             "url": "https://www.vatera.hu/y-3528306179.html", "accepted": "True"},
            {"listing_id": "3414324671", "brand": "Zsolnay", "title": "Zsolnay könyv", "sale_type": "fix",
             "price_huf": "5000", "url": "https://www.vatera.hu/z-3414324671.html", "accepted": "False",
             "reject_reason": "nem porcelan tetel"},
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=storage.FIELDS)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    def test_legacy_csv_import_is_idempotent_and_typed(self):
        with IsolatedEnv() as tmp:
            from porcelan import db, importers
            p = tmp / "run_20260916_085427" / "vatera_osszes.csv"
            p.parent.mkdir()
            self._legacy_csv(p)
            conn = db.get_conn()
            r1 = importers.import_legacy_csv(p, conn=conn)
            r2 = importers.import_legacy_csv(p, conn=conn)
            self.assertEqual(r1["new"], 3)
            self.assertEqual(r2["new"], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0], 3)
            types = conn.execute("SELECT price_type, COUNT(*) FROM price_records GROUP BY 1").fetchall()
            # csak a fix áras, elfogadott tétel lesz kínálati ár-rekord; az aukció kikiáltási ára nem
            self.assertEqual([tuple(t) for t in types], [("asking_active", 1)])
            first_seen = conn.execute("SELECT first_seen FROM listings WHERE source_id='3491251307'").fetchone()[0]
            self.assertTrue(first_seen.startswith("2026-09-16T06:54"))   # a mappanévből, UTC-ben

    def test_price_csv_validation(self):
        with IsolatedEnv() as tmp:
            from porcelan import db, importers
            p = tmp / "prices.csv"
            p.write_text("source,source_ref,market,price_type,amount,currency,observed_at,title,buyer_premium_rate\n"
                         "bav,1,HU,auction_hammer,100000,HUF,2026-05-01,Herendi váza,0.2\n"
                         "x,2,HU,becsles,5,HUF,2026-05-01,Herendi,\n", encoding="utf-8")
            res = importers.import_price_csv(p, db.get_conn())
            self.assertEqual(res["rows"], 1)
            self.assertEqual(res["skipped"], 1)

    def test_repo_snapshot_import(self):
        with IsolatedEnv():
            from porcelan import db, importers
            res = importers.import_repo_snapshot(db.get_conn())
            self.assertEqual(res["fix-aras.md"]["rows"], 1640)
            self.assertEqual(res["aukcio.md"]["rows"], 206)
            conn = db.get_conn()
            n_auction_train = conn.execute("SELECT COUNT(*) FROM price_records WHERE price_type='asking_active' "
                                           "AND listing_id IN (SELECT id FROM listings WHERE sale_type='aukcio')").fetchone()[0]
            self.assertEqual(n_auction_train, 0)      # aukciós ár nem kerül kínálati árként a tanítóadatba
            newest = conn.execute("SELECT MAX(last_seen) FROM listings").fetchone()[0]
            self.assertLess(newest, "2026-09-20")     # a kiszurt.md sem kap "most" időbélyeget


class DatasetTest(unittest.TestCase):
    def test_groups_and_split_without_leakage(self):
        import pandas as pd
        from porcelan import dataset
        df = pd.DataFrame({
            "title": ["Herendi Apponyi váza zöld 24 cm", "Herendi Apponyi váza zöld 25 cm", "Zsolnay eozin tál",
                      "Herendi nyúl figura", "Zsolnay pompadour csésze", "Herendi Rothschild tányér"] * 5,
            "dedup_key": [f"k{i}" for i in range(30)], "listing_id": [None] * 30,
            "market": ["HU"] * 30, "brand": ["Herendi", "Herendi", "Zsolnay", "Herendi", "Zsolnay", "Herendi"] * 5,
            "observed_at": pd.to_datetime(["2026-01-01"] * 30, utc=True)})

        class NoImages:
            def execute(self, *a):
                return []
        groups = dataset.assign_groups(NoImages(), df)
        self.assertEqual(groups[0], groups[1])          # közel azonos cím → egy csoport
        df["group"] = groups
        labels, info = dataset.split(df, seed=1)
        for a, b in (("train", "test"), ("train", "val"), ("val", "test")):
            self.assertFalse(set(df.group[labels == a]) & set(df.group[labels == b]))
        self.assertIn("véletlen", info["test"])
        df["observed_at"] = pd.to_datetime([f"2026-0{1 + i % 6}-01" for i in range(30)], utc=True)
        labels, info = dataset.split(df, seed=1)
        self.assertIn("időbeli", info["test"])
        self.assertGreaterEqual(df.observed_at[labels == "test"].min(), df.observed_at[labels == "train"].max())


class CostTest(unittest.TestCase):
    def _estimate(self, basis="realized"):
        return {"features": {"object_type": "vase", "size_cm": 20},
                "markets": {"HU": {"q10": 30000, "q50": 50000, "q90": 80000, "currency": "HUF", "confidence": 0.6,
                                   "basis": basis, "top_similarity": 0.9},
                            "US": {"q10": 200, "q50": 300, "q90": 450, "currency": "USD", "confidence": 0.6,
                                   "basis": basis, "top_similarity": 0.9}}}

    def test_profit_hu_and_us(self):
        with IsolatedEnv():
            from porcelan import costs
            a = costs.assumptions({"common.profit_tax_rate": 0.0, "common.risk_reserve_rate": 0.0,
                                   "common.inbound_shipping_huf": 2000, "hu.platform_fee_rate": 0.1,
                                   "hu.packaging_huf": 1000, "fx.huf_per_usd": 350})
            listing = {"price_huf": 20000, "sale_type": "fix"}
            r = costs.evaluate(listing, self._estimate(), a)
            # HU: 50000 − 20000 − 2000 − 5000 (10%) − 1000 = 22000
            self.assertEqual(r["HU"]["base"]["profit_huf"], 22000)
            self.assertLess(r["HU"]["conservative"]["profit_huf"], r["HU"]["base"]["profit_huf"])
            # US: a dollárbecslés saját árfolyammal számolódik, nem a magyar érték átváltása
            self.assertEqual(r["US"]["value_huf"]["q50"], 105000)
            self.assertGreater(r["US"]["base"]["cost_items"]["nemzetközi szállítás (kis tárgy)"], 0)
            self.assertTrue(r["HU"]["price_is_final"])

    def test_asking_basis_and_auction(self):
        with IsolatedEnv():
            from porcelan import costs, ranking
            a = costs.assumptions({"common.asking_to_sale_ratio": 0.8})
            r = costs.evaluate({"price_huf": 20000, "sale_type": "fix"}, self._estimate("asking"), a)
            self.assertEqual(r["HU"]["expected_sale_huf"], 40000)
            listing = {"price_huf": 20000, "sale_type": "aukcio", "status": "active", "relevance": "accepted",
                       "title": "Herendi váza", "description": "x"}
            est = self._estimate()
            est["features"]["brand"] = "Herendi"
            res = ranking.assess(listing, est, costs.assumptions())
            hu = res["markets"]["HU"]
            self.assertFalse(hu["price_is_final"])
            self.assertIn("aukció: az aktuális licit nem végleges vételár", hu["risks"])
            # a max. licitnél a konzervatív nyereség épp a küszöb felett van
            sc = costs.scenario("HU", hu["max_bid_huf"], 30000, "realized", listing, est["features"], costs.assumptions())
            self.assertGreaterEqual(sc["profit_huf"], 5000)

    def test_invalid_override_ignored(self):
        with IsolatedEnv():
            from porcelan import costs
            a = costs.assumptions({"fx.huf_per_usd": -5, "hu.platform_fee_rate": float("nan")})
            self.assertGreater(a["fx"]["huf_per_usd"], 0)


class ImageTest(unittest.TestCase):
    def test_phash_near_duplicate(self):
        with IsolatedEnv():
            from PIL import Image, ImageDraw
            from porcelan import images
            img = Image.new("RGB", (400, 300), "white")
            d = ImageDraw.Draw(img)
            d.ellipse((100, 50, 300, 250), fill=(30, 80, 160))
            d.rectangle((20, 20, 80, 120), fill=(200, 40, 40))
            buf1, buf2, buf3 = io.BytesIO(), io.BytesIO(), io.BytesIO()
            img.save(buf1, "JPEG", quality=95)
            img.resize((200, 150)).save(buf2, "JPEG", quality=60)
            Image.new("RGB", (400, 300), (10, 200, 10)).save(buf3, "PNG")
            a, b = images.store_image_bytes(buf1.getvalue()), images.store_image_bytes(buf2.getvalue())
            c = images.store_image_bytes(buf3.getvalue())
            self.assertNotEqual(a["sha256"], b["sha256"])
            self.assertLessEqual(images.hamming(a["phash"], b["phash"]), images.PHASH_DUP_BITS)
            self.assertGreater(images.hamming(a["phash"], c["phash"]), images.PHASH_DUP_BITS)


class ModelAndApiTest(unittest.TestCase):
    """Tanítás → verziózott mentés → betöltés → becslés → API-szűrés, CLIP nélkül (gyors)."""

    def test_end_to_end(self):
        with IsolatedEnv() as tmp:
            from porcelan import db, predict, scoring, train
            conn = db.get_conn()
            synthetic_price_records(conn)
            man = train.train(conn, n_seeds=1, use_clip=False)
            self.assertEqual(man["status"], "kísérleti")         # kínálati ár → soha nem "validált"
            self.assertTrue((tmp / "models" / man["version"] / "manifest.json").exists())
            self.assertEqual(predict.current_version(), man["version"])
            for key in ("baseline_group_median/HU", "deep_multimodal/HU", "gbm_quantile/HU"):
                self.assertIn(key, man["metrics"]["test"])
            # hirdetések és becslés az elmentett súlyokkal
            for i, (title, price, st) in enumerate([("Herendi Apponyi váza 24 cm", 9000, "fix"),
                                                    ("Zsolnay eozin figura 20 cm", 30000, "aukcio"),
                                                    ("Herendi Rothschild tányér", 45000, "alku")]):
                db.upsert_listing(conn, "vatera", str(900000000 + i), {
                    "url": f"https://www.vatera.hu/x-{900000000 + i}.html", "title": title, "price_huf": price,
                    "sale_type": st, "status": "active", "relevance": "accepted",
                    "brand": "Herendi" if "Herendi" in title else "Zsolnay"}, db.now_iso())
            conn.commit()
            est = predict.Estimator()
            out = est.predict([dict(r) for r in conn.execute("SELECT * FROM listings")], conn)
            self.assertEqual(set(out[0]["markets"]), {"HU", "US"})
            hu = out[0]["markets"]["HU"]
            self.assertLessEqual(hu["q10"], hu["q50"])
            self.assertLessEqual(hu["q50"], hu["q90"])
            self.assertEqual(out[0]["markets"]["US"]["currency"], "USD")
            s1 = scoring.score(conn)
            s2 = scoring.score(conn)
            self.assertEqual(s1["scored"], 3)
            self.assertEqual(s2["scored"], 0)           # változatlan bemenet → nincs újrabecslés

            from fastapi.testclient import TestClient
            from porcelan import api
            with TestClient(api.app) as client:
                st = client.get("/api/status").json()
                self.assertEqual(st["model"]["version"], man["version"])
                self.assertTrue(any("KÍSÉRLETI" in w for w in st["warnings"]))
                allr = client.get("/api/deals?market=HU").json()
                self.assertEqual(allr["total"], 3)
                her = client.get("/api/deals?market=HU&brand=Herendi&max_price=50000").json()
                self.assertEqual({c["title"] for c in her["items"]},
                                 {"Herendi Apponyi váza 24 cm", "Herendi Rothschild tányér"})
                auc = client.get("/api/deals?market=US&sale_type=aukcio").json()
                self.assertEqual([c["sale_type"] for c in auc["items"]], ["aukcio"])
                cheap = client.get("/api/deals?market=HU&max_price=20000").json()
                self.assertTrue(all(c["price_huf"] <= 20000 for c in cheap["items"]))
                srt = client.get("/api/deals?market=HU&sort=price_asc").json()
                prices = [c["price_huf"] for c in srt["items"]]
                self.assertEqual(prices, sorted(prices))
                lid = allr["items"][0]["id"]
                det = client.get(f"/api/listings/{lid}").json()
                self.assertEqual(det["estimate"]["model_version"], man["version"])
                self.assertIn("HU", det["assessment"]["markets"])
                self.assertEqual(client.get("/api/deals?market=XX").status_code, 422)


if __name__ == "__main__":
    unittest.main()
