"""Tanítóadat-mennyiség a célokhoz képest (settings: [targets]).

A képalapú árbecsléshez sok tízezer képes adat kell; ez a modul mutatja, hol tart
a gyűjtés: általános előtanító korpusz, Herendi/Zsolnay korpusz, realizált árak.
"""
from __future__ import annotations

from . import db, settings

REALIZED = ("realized_sale", "auction_hammer", "auction_final_bid")


def data_volume(conn=None) -> dict:
    conn = conn or db.get_conn()
    t = settings.get("targets")
    img = ("EXISTS (SELECT 1 FROM images i WHERE i.status IN ('ok','duplicate') AND "
           "(i.price_record_id=p.id OR (p.listing_id IS NOT NULL AND i.listing_id=p.listing_id)))")
    rows = conn.execute(f"SELECT COALESCE(p.corpus,'herend_zsolnay') corpus, p.market, p.price_type, COUNT(*) n, "
                        f"SUM({img}) n_img FROM price_records p GROUP BY 1,2,3").fetchall()
    by = [dict(r) for r in rows]

    def total(corpus=None, with_img=False, types=None, market=None):
        return int(sum((r["n_img"] if with_img else r["n"]) or 0 for r in by
                       if (corpus is None or r["corpus"] == corpus) and (types is None or r["price_type"] in types)
                       and (market is None or r["market"] == market)
                       and r["price_type"] not in ("auction_current_bid", "auction_start_price")))

    pending_images = conn.execute("SELECT COUNT(*) FROM images WHERE status='pending'").fetchone()[0]
    goals = [
        {"key": "general_records_with_images", "label": "Általános porcelán/kerámia kép+ár (előtanítás)",
         "have": total("general", True), "target": t["general_records_with_images"]},
        {"key": "hz_records_with_images", "label": "Herendi/Zsolnay kép+ár (finomhangolás)",
         "have": total("herend_zsolnay", True), "target": t["hz_records_with_images"]},
    ]
    for m in ("HU", "US"):
        goals.append({"key": f"realized_{m}", "label": f"Realizált ár, {m} (kalibráció/validáció)",
                      "have": total(None, False, REALIZED, m), "target": t["realized_prices_per_market"]})
    for g in goals:
        g["pct"] = round(100 * g["have"] / g["target"], 1) if g["target"] else None
    return {
        "goals": goals,
        "records": {"general": total("general"), "herend_zsolnay": total("herend_zsolnay"),
                    "general_with_images": total("general", True), "hz_with_images": total("herend_zsolnay", True)},
        "pending_image_downloads": pending_images,
        "by_corpus_market_type": by,
        "last_harvest_ebay": db.get_meta(conn, "last_harvest_ebay"),
    }
