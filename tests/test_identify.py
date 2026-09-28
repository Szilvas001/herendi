"""Pontos termékazonosítás és cikkszám-szintű piaci ár (±10% cél) tesztjei."""
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import IsolatedEnv  # noqa: E402


class IdentifyTest(unittest.TestCase):
    CASES = [
        # valós Vatera-címformák (2026-09)
        ("Herendi nagy füles porcelán díszváza – Zöld Apponyi (AV 7183)", "Herendi|7183|AV"),
        ("Herendi Apponyi Purpur 749/AP fedeles kakaós készlet - 6 személyes", "Herendi|749|AP"),
        ("Antik Herendi Viktória Mintás Csésze Aljjal 1711 / VBO Kávéscsésze", "Herendi|1711|VBO"),
        ("Herend Queen Victoria coffee cup 711-0-00 VBO", "Herendi|711|VBO"),
        ("Herend 05236-0-00 VHB rabbit", "Herendi|5236|VHB"),
        ("Egyedi Herendi 7780 ovális tálka Apponyi Orange – Ritka gyűjtői darab", "Herendi|7780|AOG"),
        ("Herendi Rothschild mintás  teás csésze + alj 1726", "Herendi|1726|RO"),
        ("6052 Herendi porcelán talpas serleg", "Herendi|6052|-"),
        # eladói kódok, évszámok, méretek NEM formaszámok
        ("Herendi virágos teás készlet (ZAL-R 91989)", None),
        ("1H511 Régi Herendi Rothschild mintás oroszlánlábas porcelán kaspó 1944", None),
        ("RITKA ! Herendi art deco figura-Viktória vizicsikón, 1941 - 51894", None),
        ("Herendi váza 1950-es évek", None),
        ("Herendi nyúl 24 cm", None),
    ]

    def test_real_title_forms(self):
        from porcelan.identify import identify_text
        for title, want in self.CASES:
            with self.subTest(title=title):
                self.assertEqual(identify_text(title).sku_key, want)

    def test_pattern_from_name(self):
        from porcelan.identify import identify_text
        self.assertEqual(identify_text("Herendi kék halpikkelyes nyúl").pattern, "VHB")
        self.assertEqual(identify_text("Herendi Viktória mintás váza 6534").sku_key, "Herendi|6534|VBO")
        self.assertEqual(identify_text("Herendi Apponyi zöld tálka (7780)").pattern, "AV")


class SkuPricingTest(unittest.TestCase):
    def test_sales_needed_formula(self):
        from porcelan.sku_model import prob_within, sales_needed
        r = sales_needed(0.3)
        # n eladás átlagának szórása σ/√n; a képlet szerinti n-nél P(±10%) ≥ 90%
        self.assertGreaterEqual(prob_within(0.3 / math.sqrt(r["n_for_share"])), 0.9)
        self.assertLess(prob_within(0.3 / math.sqrt(r["n_for_share"] - 1)), 0.9)

    def test_repeat_sales_reach_10pct_and_flag_is_reliable(self):
        """SZINTETIKUS ismételt eladások (σ=0.2, cikkszámonként 25 eladás): a módszer mechanikája.

        Ez NEM a valós pontosság mérése – azt csak valós, ismételt eladásokból lehet."""
        with IsolatedEnv():
            from porcelan import catalog, db, sku_model
            conn = db.get_conn()
            rnd = random.Random(3)
            forms = [(7183, "AV"), (749, "AP"), (1711, "VBO"), (5236, "VHB"), (6052, "RO"), (7780, "AOG")]
            for form, pat in forms:
                true_price = rnd.uniform(20000, 150000)
                for k in range(25):
                    price = true_price * math.exp(rnd.gauss(0, 0.2))
                    title = f"Herendi porcelán {form}/{pat} tétel {k}{form}"
                    db.upsert_price_record(conn, {
                        "source": "synthetic", "source_ref": f"{form}-{k}", "market": "HU",
                        "price_type": "auction_final_bid", "amount": round(price), "currency": "HUF",
                        "price_huf": round(price), "observed_at": "2026-09-16T12:00:00+00:00", "title": title,
                        "brand": "Herendi", "object_type": "other", "condition": "ismeretlen",
                        "dedup_key": f"{form}-{k}", "provenance": {"note": "szintetikus tesztadat"}})
            conn.commit()
            # realizált ár csak ≥200 rekordtól lesz célváltozó; 150 rekord → kínálati-ár ág nem érintett
            import porcelan.dataset as dsmod
            old = dsmod.MIN_REALIZED_FOR_BASIS
            dsmod.MIN_REALIZED_FOR_BASIS = 100
            try:
                ident = catalog.identify_all_text(conn)
                self.assertEqual(ident["records_sku"], 150)
                res = sku_model.evaluate(conn)
            finally:
                dsmod.MIN_REALIZED_FOR_BASIS = old
            hu = res["by_market"]["HU"]
            self.assertEqual(hu["n"], 150)
            sig = res["params"]["sigma_by_market"]["HU"]["sigma"]
            self.assertAlmostEqual(sig, 0.2, delta=0.06)           # a piaci szórást az adatból becsüli
            # egy EGYEDI eladás árához mért hiba nem mehet a piaci zajszint (~14% σ=0.2-nél) alá
            self.assertGreater(hu["mdape"], 0.10)
            self.assertLess(hu["mdape"], 0.20)
            # a TERMÉK PIACI ÁRÁHOZ mért hiba elegendő azonos-termék eladással 10% alá megy
            curve = res["market_price_curve"]["HU"]
            self.assertGreater(curve["1"]["mdape"], 0.10)
            self.assertLess(curve["10"]["mdape"], 0.10)
            self.assertGreater(curve["20"]["within_10pct"], curve["1"]["within_10pct"])


class ImageIdentificationTest(unittest.TestCase):
    def test_vote(self):
        import numpy as np
        from porcelan.catalog import _vote
        sims = np.array([0.95, 0.94, 0.6, 0.5, 0.4])
        best, score, margin = _vote(sims, ["A", "A", "B", "C", "C"])
        self.assertEqual(best, "A")
        self.assertGreater(score, 0.9)


if __name__ == "__main__":
    unittest.main()


class NoSelfEvidenceTest(unittest.TestCase):
    def test_own_record_excluded(self):
        import pandas as pd
        from porcelan.sku_model import SkuPricer
        df = pd.DataFrame({"sku_key": ["Herendi|711|VBO", "Herendi|711|VBO"], "form_key": ["Herendi|711"] * 2,
                           "pattern_code": ["VBO"] * 2, "market": ["HU"] * 2, "y_log": [10.0, 10.5],
                           "condition": ["ismeretlen"] * 2, "group": ["s1", "s2"], "source_ref": ["111", "222"],
                           "observed_at": pd.to_datetime(["2026-09-16"] * 2, utc=True)})
        est = SkuPricer(df).estimate("HU", "Herendi|711|VBO", "ismeretlen", exclude_refs={"111"})
        self.assertEqual(est["n_exact"], 1)            # csak a MÁSIK eladás számít
        self.assertAlmostEqual(est["mu"], 10.5)
