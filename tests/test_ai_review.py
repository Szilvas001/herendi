"""Az AI réteg tesztjei – valódi API hívás nélkül, stub klienssel."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from porcelan import ai_review, config  # noqa: E402


class FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class FakeMessage:
    stop_reason = "end_turn"
    stop_details = None
    usage = None

    def __init__(self, payload):
        self.content = [FakeBlock(json.dumps(payload, ensure_ascii=False))]


class FakeStream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class FakeMessages:
    """A modell minden adagban az első hirdetést választja ki, plusz egy hamisat."""

    def __init__(self, recorder, beta_supported=True):
        self.recorder = recorder
        self.beta_supported = beta_supported

    def stream(self, **kwargs):
        if kwargs.pop("betas", None) is not None and not self.beta_supported:
            raise TypeError("ismeretlen beta")
        self.recorder.append(kwargs)
        sent = json.loads(kwargs["messages"][0]["content"].split("Hirdetések JSON-ban:\n")[1]
                          .split("\n\n")[0])
        picks = [{
            "listing_id": sent[0]["listing_id"], "url": sent[0]["url"],
            "cim": sent[0]["title"], "marka": sent[0]["brand"],
            "eladasi_tipus": sent[0]["sale_type"], "ar_huf": sent[0]["price_huf"] or 0,
            "kategoria": "aron_aluli", "becsult_ertek_eur_min": 100,
            "becsult_ertek_eur_max": 200, "bizalom": "magas",
            "indoklas": "teszt", "kockazatok": "",
        }, {
            "listing_id": "999", "url": "https://www.vatera.hu/kitalalt-999.html",
            "cim": "hallucinált", "marka": "Herendi", "eladasi_tipus": "fix",
            "ar_huf": 1, "kategoria": "aron_aluli", "becsult_ertek_eur_min": 1,
            "becsult_ertek_eur_max": 2, "bizalom": "alacsony",
            "indoklas": "nem a bemenetből", "kockazatok": "",
        }]
        return FakeStream(FakeMessage({"talalatok": picks, "osszegzes": "ok"}))


class FakeClient:
    def __init__(self, beta_supported=True):
        self.calls: list[dict] = []
        self.messages = FakeMessages(self.calls, beta_supported=True)
        self.beta = type("Beta", (), {"messages": FakeMessages(self.calls, beta_supported)})()


def make_buckets():
    def rec(i, sale_type):
        return {
            "listing_id": str(i), "brand": "Herendi", "title": f"Herendi tétel {i}",
            "sale_type": sale_type, "price_huf": 1000 * i, "price_kind": "fix ar",
            "buy_now_huf": None, "start_bid_huf": None, "current_bid_huf": None,
            "bid_count": None, "offer_possible": False, "end_time": None,
            "damage_flags": "", "suspect_flags": "", "decor_hints": "",
            "description": "leírás", "url": f"https://www.vatera.hu/tetel-{i}.html",
        }

    return {
        config.SALE_AUCTION: [rec(1, config.SALE_AUCTION), rec(2, config.SALE_AUCTION)],
        config.SALE_FIX: [rec(3, config.SALE_FIX)],
        config.SALE_OFFER: [rec(4, config.SALE_OFFER)],
    }


class AnalyseTest(unittest.TestCase):
    def test_three_parts_and_url_validation(self):
        client = FakeClient()
        result = ai_review.analyse(make_buckets(), chunk_size=10, client=client)

        # Eladási típusonként egy-egy hívás -> 3 rész.
        self.assertEqual(len(client.calls), 3)
        for call, sale_type in zip(client.calls, config.SALE_TYPES):
            head = call["messages"][0]["content"].splitlines()[0]
            self.assertTrue(head.startswith(
                f"Eladási típus: {config.SALE_TYPE_LABELS[sale_type]} ({sale_type})"), head)

        # A kitalált URL-eket eldobjuk, a valódiakat megtartjuk.
        urls = [p["url"] for p in result["talalatok"]]
        self.assertEqual(len(urls), 3)
        self.assertNotIn("https://www.vatera.hu/kitalalt-999.html", urls)
        self.assertTrue(all(u.startswith("https://www.vatera.hu/tetel-") for u in urls))
        self.assertEqual(set(result["osszegzesek"]), set(config.SALE_TYPES))
        self.assertEqual(result["hibak"], [])

    def test_request_params(self):
        client = FakeClient()
        ai_review.analyse(make_buckets(), chunk_size=10, client=client)
        call = client.calls[0]
        self.assertEqual(call["model"], config.CLAUDE_MODEL)
        self.assertEqual(call["thinking"], {"type": "adaptive"})
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
        self.assertIn("Herendi", call["system"])

    def test_chunking(self):
        client = FakeClient()
        ai_review.analyse(make_buckets(), chunk_size=1, client=client)
        self.assertEqual(len(client.calls), 4)   # 2 aukciós adag + 1 fix + 1 alku

    def test_falls_back_when_beta_unavailable(self):
        client = FakeClient(beta_supported=False)
        result = ai_review.analyse(make_buckets(), chunk_size=10, client=client)
        self.assertEqual(len(result["talalatok"]), 3)

    def test_api_error_is_collected_not_raised(self):
        class Boom(FakeMessages):
            def stream(self, **kwargs):
                raise RuntimeError("429 rate limit")

        client = FakeClient()
        client.beta.messages = Boom(client.calls)
        client.messages = Boom(client.calls)
        result = ai_review.analyse(make_buckets(), chunk_size=10, client=client)
        self.assertEqual(result["talalatok"], [])
        self.assertEqual(len(result["hibak"]), 3)


if __name__ == "__main__":
    unittest.main()
