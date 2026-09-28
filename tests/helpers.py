"""Közös tesztsegédek: elkülönített adatkönyvtár és beállítások tesztenként."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FIX = Path(__file__).parent / "fixtures"


class IsolatedEnv:
    """HZ_DATA_DIR / HZ_MODELS_DIR / HZ_SETTINGS átirányítása ideiglenes könyvtárba."""

    def __init__(self, settings_file: Path | None = None):
        self.settings_file = settings_file

    def __enter__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hz_test_"))
        self.old = {k: os.environ.get(k) for k in ("HZ_DATA_DIR", "HZ_MODELS_DIR", "HZ_SETTINGS")}
        os.environ["HZ_DATA_DIR"] = str(self.tmp / "data")
        os.environ["HZ_MODELS_DIR"] = str(self.tmp / "models")
        os.environ["HZ_SETTINGS"] = str(self.settings_file or (self.tmp / "none.toml"))
        from porcelan import settings
        settings.reload()
        return self.tmp

    def __exit__(self, *exc):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        from porcelan import settings
        settings.reload()
        shutil.rmtree(self.tmp, ignore_errors=True)


def synthetic_price_records(conn, n_hu=160, n_us=60, seed=0):
    """SZINTETIKUS ár-rekordok – kizárólag a modellbetöltés/tanítás mechanikájának tesztjéhez."""
    import random
    from porcelan import db, text
    rnd = random.Random(seed)
    kinds = [("váza", 30000), ("figura", 45000), ("tányér", 9000), ("bonbonier", 15000), ("teáskészlet", 80000)]
    decors = ["Apponyi", "Rothschild", "Viktória", "eozin", ""]
    for market, n, cur, scale in (("HU", n_hu, "HUF", 1.0), ("US", n_us, "USD", 1 / 250)):
        for i in range(n):
            brand = rnd.choice(["Herendi", "Zsolnay"])
            kind, base = rnd.choice(kinds)
            dec = rnd.choice(decors)
            size = rnd.randint(8, 35)
            title = f"{brand} {dec} {kind} {size} cm #{i}"
            price = base * (1 + size / 30) * rnd.uniform(0.7, 1.3) * scale
            f = text.extract(title)
            db.upsert_price_record(conn, {
                "source": "synthetic", "source_ref": f"{market}-{i}", "market": market,
                "price_type": "asking_active", "amount": round(price, 2), "currency": cur,
                "observed_at": "2026-09-16T12:00:00+00:00", "title": title, "brand": f["brand"],
                "object_type": f["object_type"], "decor": f["decor"], "size_cm": f["size_cm"],
                "pieces": f["pieces"], "condition": f["condition"], "dedup_key": f"{market}-{i}",
                "provenance": {"note": "szintetikus tesztadat"}})
    conn.commit()


def synthetic_general_records(conn, n=700, seed=5):
    """SZINTETIKUS általános porcelán korpusz – csak a kétlépcsős tanítás mechanikájához."""
    import random
    from porcelan import db, text
    rnd = random.Random(seed)
    kinds = [("vase", 40), ("figurine", 60), ("plate", 15), ("teapot", 35), ("bowl", 20)]
    for i in range(n):
        kind, base = rnd.choice(kinds)
        size = rnd.randint(8, 40)
        title = f"Vintage porcelain {kind} hand painted {size} cm lot{i}"
        f = text.extract(title)
        price = base * (1 + size / 25) * rnd.uniform(0.7, 1.3)
        db.upsert_price_record(conn, {
            "source": "synthetic_general", "source_ref": f"g{i}", "market": "US", "price_type": "asking_active",
            "amount": round(price, 2), "currency": "USD", "observed_at": "2026-09-16T12:00:00+00:00",
            "title": title, "brand": None, "object_type": f["object_type"], "size_cm": f["size_cm"],
            "condition": f["condition"], "dedup_key": f"g{i}", "corpus": "general",
            "provenance": {"note": "szintetikus tesztadat"}})
    conn.commit()
