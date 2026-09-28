"""Adatpontok betöltése a PostgreSQL-be a helyi SQLite-ból és az új forrásokból.

Csak az a tétel kerül át, amelyiknek legalább három képe, érdemi leírása és ára
van. A forrás a partíciót választja ki, így minden hely külön táblába ír.
"""
from __future__ import annotations

import logging

from . import db, pg

log = logging.getLogger(__name__)

# A SQLite-ban az ár több mezőben lehet; ez a sorrend dönti el, mi számít árnak.
ARFORRAS = (
    ("auction_final_bid", "current_bid_huf", "aukcio lezárult licittel"),
    ("asking_active", "price_huf", "aktív hirdetés kínálati ára"),
    ("auction_start_price", "start_bid_huf", "aukció kikiáltási ára"),
)


def _ar(sor) -> tuple[int, str] | None:
    if sor["status"] == "sold" and sor["sale_type"] == "aukcio" and sor["current_bid_huf"]:
        return int(sor["current_bid_huf"]), "auction_final_bid"
    if sor["price_huf"]:
        tipus = "auction_start_price" if sor["sale_type"] == "aukcio" else "asking_active"
        if sor["status"] == "sold":
            tipus = "realized_sale"
        return int(sor["price_huf"]), tipus
    if sor["current_bid_huf"]:
        return int(sor["current_bid_huf"]), "auction_current_bid"
    return None


def vatera_atemel(conn_sqlite=None, pgconn=None, min_kep: int = 3) -> dict:
    """A helyi SQLite Vatera-adatából a feltételeknek megfelelő tételek átemelése."""
    conn_sqlite = conn_sqlite or db.get_conn()
    sajat = pgconn is None
    pgconn = pgconn or pg.connect()
    try:
        pg.sema_letrehoz(pgconn)
        pg.particio_biztosit(pgconn, "vatera")

        sorok = conn_sqlite.execute(
            "SELECT l.*, (SELECT COUNT(*) FROM images i WHERE i.listing_id=l.id) AS kepszam "
            "FROM listings l WHERE l.source='vatera' AND l.relevance<>'rejected' "
            "AND l.description IS NOT NULL AND length(trim(l.description))>=20 "
            "GROUP BY l.id HAVING kepszam >= ?", (min_kep,)).fetchall()

        stat = {"megvizsgalt": len(sorok), "bekerult": 0, "kihagyva_ar": 0, "kihagyva_egyeb": 0}
        for sor in sorok:
            ar = _ar(sor)
            if ar is None:
                stat["kihagyva_ar"] += 1
                continue
            osszeg, tipus = ar
            kepek = [{"url": r["url"], "sha256": r["sha256"], "width": r["width"],
                      "height": r["height"], "local_path": r["path"]}
                     for r in conn_sqlite.execute(
                         "SELECT url, sha256, width, height, path FROM images "
                         "WHERE listing_id=? ORDER BY position, id", (sor["id"],))]
            adatpont = {
                "source": "vatera", "source_id": str(sor["source_id"]), "url": sor["url"],
                "market": "HU", "title": sor["title"] or "", "description": sor["description"] or "",
                "category": sor["category"], "price_huf": osszeg, "price_type": tipus,
                "price_amount": osszeg, "currency": sor["currency"] or "HUF",
                "sale_type": sor["sale_type"], "end_time": sor["end_time"],
                "brand": sor["brand"], "object_type": sor["object_type"], "decor": sor["decor"],
                "size_cm": sor["size_cm"], "pieces": sor["pieces"], "condition": sor["condition"],
                "relevance": sor["relevance"],
                "corpus": "herend_zsolnay" if sor["brand"] else "general",
                "observed_at": sor["last_checked"] or sor["last_seen"],
                "images": kepek,
                "raw": {"status": sor["status"], "status_reason": sor["status_reason"],
                        "bid_count": sor["bid_count"], "relevance": sor["relevance"],
                        "mark_flags": sor["mark_flags"], "damage_flags": sor["damage_flags"]},
            }
            if pg.beir(pgconn, adatpont):
                stat["bekerult"] += 1
            else:
                stat["kihagyva_egyeb"] += 1
        return stat
    finally:
        if sajat:
            pgconn.close()


def adatpontokat_beir(source: str, adatpontok, pgconn=None) -> dict:
    """Egy scraper által előállított adatpontok beírása a forrás partíciójába."""
    sajat = pgconn is None
    pgconn = pgconn or pg.connect()
    try:
        pg.sema_letrehoz(pgconn)
        pg.particio_biztosit(pgconn, source)
        stat = {"megvizsgalt": 0, "bekerult": 0, "kihagyva": 0, "okok": {}}
        for adatpont in adatpontok:
            stat["megvizsgalt"] += 1
            ok = pg.ervenyes(adatpont)
            if ok is not None:
                stat["kihagyva"] += 1
                stat["okok"][ok] = stat["okok"].get(ok, 0) + 1
                continue
            stat["bekerult"] += int(pg.beir(pgconn, adatpont))
        return stat
    finally:
        if sajat:
            pgconn.close()
