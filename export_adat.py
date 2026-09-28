"""Konzisztens adat-pillanatkép a repóba (a bejárás közben is biztonságos).

Az adatbázis WAL módban fut és a crawler írja, ezért nem sima fájlmásolatot
készítünk: a `VACUUM INTO` a tranzakciókkal konzisztens, tömörített másolatot ad.
A kimenet gzippelve kerül a `data_export/` mappába, mellette egy rövid
összefoglaló, hogy a fájl megnyitása nélkül is látszódjon a tartalma.
"""
from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

from porcelan import db, settings

ROOT = Path(__file__).resolve().parent
KI = ROOT / "data_export"


def main() -> None:
    KI.mkdir(exist_ok=True)
    tmp = Path(tempfile.mkdtemp()) / "snapshot.sqlite"
    forras = settings.path("db_file")
    with sqlite3.connect(f"file:{forras}?mode=ro", uri=True) as conn:
        conn.execute("VACUUM INTO ?", (str(tmp),))

    cel = KI / "hzfinder.sqlite.gz"
    with tmp.open("rb") as be, gzip.open(cel, "wb", compresslevel=9) as ki:
        shutil.copyfileobj(be, ki)
    meret = cel.stat().st_size

    c = db.get_conn()
    q = lambda s: c.execute(s).fetchone()[0]  # noqa: E731
    osszefoglalo = {
        "keszult": db.now_iso(),
        "hirdetes": q("SELECT COUNT(*) FROM listings"),
        "elfogadott": q("SELECT COUNT(*) FROM listings WHERE relevance='accepted'"),
        "herendi": q("SELECT COUNT(*) FROM listings WHERE brand='Herendi'"),
        "zsolnay": q("SELECT COUNT(*) FROM listings WHERE brand='Zsolnay'"),
        "termekoldal_letoltve": q("SELECT COUNT(*) FROM listings WHERE last_checked IS NOT NULL"),
        "ar_rekord": q("SELECT COUNT(*) FROM price_records"),
        "realizalt_zaro_licit": q("SELECT COUNT(*) FROM price_records WHERE price_type='auction_final_bid'"),
        "kep_url": q("SELECT COUNT(*) FROM images"),
        "pillanatkep_bajt": meret,
        "megjegyzes": "A képfájlok (data/images) és a HTTP-cache nincsenek a pillanatképben, "
                      "csak a rekordok és a kép-URL-ek.",
    }
    (KI / "osszefoglalo.json").write_text(json.dumps(osszefoglalo, ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    print(json.dumps(osszefoglalo, ensure_ascii=False, indent=2))
    shutil.rmtree(tmp.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
