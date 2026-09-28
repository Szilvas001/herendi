"""Nagy léptékű adatgyűjtés és -feldolgozás tesztjei (hálózat nélkül, szimulált API-val)."""
import os
import random
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import FIX, IsolatedEnv  # noqa: E402


class FakeResp:
    def __init__(self, data, status=200):
        self._data, self.status_code = data, status

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeEbay:
    """Szimulált Browse API: 10 000-es lapozási korláttal, ár-szűréssel."""

    def __init__(self, n=25000, seed=1, quota=None):
        rnd = random.Random(seed)
        self.items = []
        for i in range(n):
            price = round(min(40000, max(1.0, rnd.lognormvariate(3.5, 1.3))), 2)
            kind = rnd.random()
            title = ("Herend Porcelain Rabbit Figurine" if kind < 0.05 else
                     "Zsolnay Eosin Vase" if kind < 0.07 else
                     "Herend style replica bird" if kind < 0.08 else
                     f"Vintage porcelain figurine {i}")
            self.items.append({"itemId": f"v1|{i}|0", "title": title, "price": {"value": str(price), "currency": "USD"},
                               "image": {"imageUrl": f"https://i.ebayimg.com/{i}.jpg"},
                               "additionalImages": [{"imageUrl": f"https://i.ebayimg.com/{i}b.jpg"}],
                               "conditionId": "3000", "itemWebUrl": f"https://www.ebay.com/itm/{i}"})
        self.calls = 0
        self.quota = quota

    def post(self, url, **kw):
        return FakeResp({"access_token": "t", "expires_in": 7200})

    def get(self, url, params=None, **kw):
        self.calls += 1
        if self.quota is not None and self.calls > self.quota:
            return FakeResp({}, 429)
        lo, hi = map(float, re.search(r"price:\[([\d.]+)\.\.([\d.]+)\]", params["filter"]).groups())
        sel = [it for it in self.items if lo <= float(it["price"]["value"]) <= hi]
        off, lim = int(params["offset"]), int(params["limit"])
        assert off + lim <= 10000 + 200, "az API 10 000-es korlátján túl lapozna"
        page = sel[off:off + lim] if off < 10000 else []
        return FakeResp({"total": len(sel), "itemSummaries": page,
                         "next": "x" if off + lim < min(len(sel), 10000) else None})


class HarvestTest(unittest.TestCase):
    def setUp(self):
        os.environ["EBAY_CLIENT_ID"], os.environ["EBAY_CLIENT_SECRET"] = "id", "secret"

    def _settings(self, tmp):
        p = tmp / "s.toml"
        p.write_text('[ebay_harvest]\nqueries_herend_zsolnay = []\nqueries_general = ["porcelain"]\n'
                     'min_delay_sec = 0\nmax_calls_per_run = 100000\n')
        return p

    def test_adaptive_price_slicing_collects_everything(self):
        with IsolatedEnv() as tmp:
            os.environ["HZ_SETTINGS"] = str(self._settings(tmp))
            from porcelan import db, settings
            settings.reload()
            from porcelan.harvest import EbayHarvester
            api = FakeEbay(25000)
            conn = db.get_conn()
            res = EbayHarvester(conn, session=api, sleep=0).run()
            self.assertEqual(res["status"], "completed")
            self.assertGreater(res["stats"]["slices_split"], 0)          # 25 000 > 10 000: fel kellett bontani
            self.assertEqual(res["summary"]["truncated_slices"], 0)
            self.assertTrue(res["summary"]["complete"])
            n = conn.execute("SELECT COUNT(*) FROM price_records WHERE source='ebay_browse'").fetchone()[0]
            fakes = sum("replica" in it["title"] for it in api.items)
            self.assertEqual(n, 25000 - fakes)                            # minden tétel, utánzat nélkül
            corp = dict(conn.execute("SELECT corpus, COUNT(*) FROM price_records GROUP BY 1").fetchall())
            self.assertGreater(corp["general"], 20000)
            self.assertGreater(corp["herend_zsolnay"], 1000)
            imgs = conn.execute("SELECT COUNT(*) FROM images WHERE price_record_id IS NOT NULL").fetchone()[0]
            self.assertEqual(imgs, 2 * n)
            # ismételt futás: nincs új rekord, nincs duplikátum
            res2 = EbayHarvester(conn, session=api, sleep=0).run()
            self.assertEqual(res2["stats"]["new_records"], 0)

    def test_quota_interrupt_and_resume(self):
        with IsolatedEnv() as tmp:
            os.environ["HZ_SETTINGS"] = str(self._settings(tmp))
            from porcelan import db, settings
            settings.reload()
            from porcelan.harvest import EbayHarvester
            conn = db.get_conn()
            r1 = EbayHarvester(conn, session=FakeEbay(12000, quota=20), sleep=0).run()
            self.assertEqual(r1["status"], "interrupted")
            n1 = conn.execute("SELECT COUNT(*) FROM price_records").fetchone()[0]
            r2 = EbayHarvester(conn, session=FakeEbay(12000), sleep=0).run()
            self.assertEqual(r2["status"], "completed")
            n2 = conn.execute("SELECT COUNT(*) FROM price_records").fetchone()[0]
            self.assertGreater(n2, n1)
            fakes = sum("replica" in it["title"] for it in FakeEbay(12000).items)
            self.assertEqual(n2, 12000 - fakes)


class GeneralCorpusCrawlTest(unittest.TestCase):
    def test_general_corpus_card_level_records(self):
        crawl = FIX / "crawl"
        with IsolatedEnv() as tmp:
            s = tmp / "s.toml"
            s.write_text('[vatera]\nuse_search = true\nsitemap_url = ""\n'
                         'seed_categories = []\ngeneral_categories = []\n'
                         'queries_general_corpus = ["herendi"]\n'
                         '[http]\nmin_delay_sec = 0\n')
            os.environ["HZ_SETTINGS"] = str(s)
            from porcelan import db, settings
            settings.reload()
            from porcelan.crawler import Crawler
            from porcelan.net import Fetcher
            conn = db.get_conn()
            res = Crawler("vatera", conn, fetcher=Fetcher(offline_dir=crawl, min_delay=0), corpus="general").run()
            self.assertEqual(res["stats"]["cards"], 5)
            rows = conn.execute("SELECT source_ref, price_type, corpus FROM price_records WHERE price_type='asking_active'"
                                ).fetchall()
            refs = {r["source_ref"] for r in rows}
            self.assertIn("300000001", refs)
            self.assertNotIn("300000003", refs)       # utánzat
            self.assertNotIn("300000002", refs)       # aukció


class ScalableGroupingTest(unittest.TestCase):
    def test_lsh_grouping_matches_bruteforce_on_near_duplicates(self):
        import pandas as pd
        from porcelan import dataset
        rnd = random.Random(0)
        words = ["herendi", "porcelán", "váza", "apponyi", "zöld", "figura", "nyúl", "madár", "tányér", "rothschild",
                 "kézzel", "festett", "jelzett", "antik", "régi", "bonbonier", "fedeles", "kis", "nagy", "pár"]
        titles = []
        for i in range(3000):
            base = rnd.sample(words, 6) + [f"x{i}"]
            titles.append(" ".join(base))
        # 300 közel-duplikátum: ugyanaz a cím, egy szó sorrendcserével
        for i in range(300):
            t = titles[i].split()
            t[0], t[1] = t[1], t[0]
            titles.append(" ".join(t))
        df = pd.DataFrame({"title": titles, "dedup_key": [f"k{i}" for i in range(len(titles))],
                           "listing_id": [None] * len(titles), "market": "HU", "brand": "Herendi"})

        class NoImages:
            def execute(self, *a):
                return []
        g = dataset.assign_groups(NoImages(), df)
        same = sum(g[i] == g[3000 + i] for i in range(300))
        self.assertEqual(same, 300)                      # minden közel-duplikátum egy csoportban
        self.assertGreater(len(set(g)), 2500)            # a különböző címek nem olvadnak össze


if __name__ == "__main__":
    unittest.main()


class TwoStageTrainingTest(unittest.TestCase):
    def test_pretrain_finetune_and_learning_curve(self):
        with IsolatedEnv():
            from helpers import synthetic_general_records, synthetic_price_records
            from porcelan import db, predict, train
            conn = db.get_conn()
            synthetic_price_records(conn, n_hu=200, n_us=120)
            synthetic_general_records(conn, n=700)
            man = train.train(conn, n_seeds=1, use_clip=False)
            self.assertEqual(man["train_rows"]["pretrain"], 700)
            self.assertIn("deep_pretrained_ft/US", man["metrics"]["test"])
            self.assertTrue(any("képes" in r for r in man["status_reasons"]))   # adatmennyiségi kapu
            # a becsléshez tárolt index csak a Herendi/Zsolnay sorokat tartalmazza
            est = predict.Estimator()
            self.assertEqual(len(est.records), 320 - 0)
            self.assertTrue(set(est.records.corpus) == {"herend_zsolnay"})
            lc = train.learning_curve(conn, fractions=(0.3, 0.6, 1.0), use_clip=False, n_seeds=1)
            variants = {(r["variant"], r["market"]) for r in lc["rows"]}
            self.assertIn(("hz_only", "HU"), variants)
            self.assertIn(("pretrained", "US"), variants)
            sizes = [r["train_rows"] for r in lc["rows"] if r["variant"] == "hz_only" and r["market"] == "HU"]
            self.assertEqual(sizes, sorted(sizes))
            self.assertIn("HU/hz_only", lc["fits"])


class VolumeTest(unittest.TestCase):
    def test_goals(self):
        with IsolatedEnv():
            from helpers import synthetic_general_records
            from porcelan import db, volume
            conn = db.get_conn()
            synthetic_general_records(conn, n=50)
            v = volume.data_volume(conn)
            g = {x["key"]: x for x in v["goals"]}
            self.assertEqual(v["records"]["general"], 50)
            self.assertEqual(g["general_records_with_images"]["have"], 0)   # kép nélkül nem számít
