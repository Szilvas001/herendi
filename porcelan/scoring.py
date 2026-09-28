"""Becslések előállítása és a teljes feldolgozási lánc.

Adatgyűjtés → tisztítás → képfeldolgozás → azonosítás → árbecslés →
(költségszámítás és rangsor: lekérdezéskor, az aktuális feltételezésekkel) → dashboard.

A becslés a hirdetés tartalmától (cím, leírás, kategória, képek) és a
modellverziótól függ, az ártól nem. Ezért árváltozáskor nem kell újrabecsülni;
változatlan tartalomra és modellre a korábbi becslés marad (input_hash).
"""
from __future__ import annotations

import hashlib
import json
import logging

from . import costs, db, ranking
from .predict import get_estimator

log = logging.getLogger(__name__)
FEATURE_VERSION = "3"


def input_hash(conn, row) -> str:
    shas = [r["sha256"] for r in conn.execute("SELECT sha256 FROM images WHERE listing_id=? AND sha256 IS NOT NULL "
                                              "ORDER BY position", (row["id"],))]
    # azonosított terméknél az azonos cikkszámú eladások száma is bemenet (új eladás → újrabecslés)
    n_sku = 0
    if row["sku_key"]:
        n_sku = conn.execute("SELECT COUNT(*) FROM price_records WHERE sku_key=? OR (form_no=? AND sku_key LIKE ?)",
                             (row["sku_key"], row["form_no"], row["sku_key"].split("|")[0] + "|%")).fetchone()[0]
    payload = json.dumps([FEATURE_VERSION, row["title"], row["description"], row["category"], shas,
                          row["sku_key"], n_sku], ensure_ascii=False)
    return hashlib.sha1(payload.encode()).hexdigest()


def score(conn=None, force: bool = False, progress=None, only_active: bool = True) -> dict:
    conn = conn or db.get_conn()
    progress = progress or (lambda f, m: log.info(m))
    est = get_estimator(reload=True)
    where = "relevance='accepted'" + (" AND status='active'" if only_active else "")
    rows = conn.execute(f"SELECT * FROM listings WHERE {where}").fetchall()
    existing = {r["listing_id"]: r["input_hash"] for r in
                conn.execute("SELECT listing_id, input_hash FROM estimates WHERE model_version=?", (est.version,))}
    todo = []
    for r in rows:
        h = input_hash(conn, r)
        if force or existing.get(r["id"]) != h:
            todo.append((r, h))
    stats = {"listings": len(rows), "scored": 0, "unchanged": len(rows) - len(todo), "model_version": est.version}
    progress(0.0, f"{len(todo)} hirdetés becslése ({stats['unchanged']} változatlan, kihagyva)")
    for i in range(0, len(todo), 256):
        batch = todo[i:i + 256]
        preds = est.predict([dict(r) for r, _ in batch], conn)
        now = db.now_iso()
        conn.executemany("INSERT OR REPLACE INTO estimates(listing_id, model_version, input_hash, created_at, payload) "
                         "VALUES(?,?,?,?,?)",
                         [(r["id"], est.version, h, now, json.dumps(p, ensure_ascii=False)) for (r, h), p in zip(batch, preds)])
        conn.commit()
        stats["scored"] += len(batch)
        progress(min(1.0, (i + len(batch)) / len(todo)), f"{i + len(batch)}/{len(todo)} becsülve")
    stats["logged_recommendations"] = log_recommendations(conn, est.version)
    db.set_meta(conn, "last_scoring", {"at": db.now_iso(), **stats})
    return stats


def load_estimate(conn, listing_id: int, version: str) -> dict | None:
    r = conn.execute("SELECT payload, input_hash, created_at FROM estimates WHERE listing_id=? AND model_version=?",
                     (listing_id, version)).fetchone()
    if not r:
        return None
    p = json.loads(r["payload"])
    p["input_hash"], p["estimated_at"] = r["input_hash"], r["created_at"]
    return p


def log_recommendations(conn, version: str) -> int:
    """Az alapfeltételezésekkel adott ajánlások naplózása (változáskor)."""
    a = costs.assumptions()
    n = 0
    rows = conn.execute("SELECT l.*, e.payload FROM listings l JOIN estimates e ON e.listing_id=l.id "
                        "AND e.model_version=? WHERE l.status='active' AND l.relevance='accepted'", (version,)).fetchall()
    for r in rows:
        res = ranking.assess(dict(r), json.loads(r["payload"]), a)
        for market, m in res["markets"].items():
            last = conn.execute("SELECT price_huf, recommended FROM recommendation_log WHERE listing_id=? AND market=? "
                                "AND model_version=? ORDER BY id DESC LIMIT 1", (r["id"], market, version)).fetchone()
            if last and last["price_huf"] == r["price_huf"] and bool(last["recommended"]) == m["recommended"]:
                continue
            conn.execute("INSERT INTO recommendation_log(listing_id, model_version, logged_at, market, price_huf, "
                         "sale_type, value_q50_huf, conservative_profit_huf, max_bid_huf, recommended) "
                         "VALUES(?,?,?,?,?,?,?,?,?,?)",
                         (r["id"], version, db.now_iso(), market, r["price_huf"], r["sale_type"],
                          m["value_huf"]["q50"], (m.get("conservative") or {}).get("profit_huf"), m["max_bid_huf"],
                          int(m["recommended"])))
            n += 1
    conn.commit()
    return n


def evaluate_recommendations(conn=None) -> dict:
    """Ajánlások utólagos ellenőrzése lezárult aukciók záróárával (HU).

    Találat: az aukció záró licitje (a tárgy tényleges magyar piaci ára) mellett
    az ajánláskori áron való vétel a költségek után is nyereséges lett volna.
    Csak licittel lezárult aukcióra mérhető; a fix áras "elkelt" jelzés ára nem
    független piaci bizonyíték."""
    conn = conn or db.get_conn()
    a = costs.assumptions()
    q = ("SELECT r.*, p.price_huf AS final_huf FROM recommendation_log r JOIN price_records p "
         "ON p.listing_id=r.listing_id AND p.price_type='auction_final_bid' WHERE r.market='HU' AND r.recommended=1 "
         "AND r.id IN (SELECT MAX(id) FROM recommendation_log WHERE recommended=1 GROUP BY listing_id, market)")
    rows = conn.execute(q).fetchall()
    hits = 0
    details = []
    for r in rows:
        listing = dict(conn.execute("SELECT * FROM listings WHERE id=?", (r["listing_id"],)).fetchone())
        feats = {"object_type": None}
        res = costs.scenario("HU", r["price_huf"], r["final_huf"], "realized", listing, feats, a)
        hit = res["profit_huf"] >= 0
        hits += hit
        details.append({"listing_id": r["listing_id"], "price_at_recommendation": r["price_huf"],
                        "final_bid": r["final_huf"], "hit": hit})
    n = len(rows)
    return {"n": n, "precision": (hits / n) if n else None, "details": details,
            "note": "Nincs még ellenőrizhető ajánlás." if not n else ""}
