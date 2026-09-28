"""Meglévő adatok importja: régi scrape CSV-k, riport-táblák, összehasonlító árak.

Minden import idempotens (forrás + azonosító szerint upsert), és megőrzi a
forrásfájlt, a megfigyelés idejét és az ár típusát.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from . import db, settings, text
from .sources.base import parse_hu_datetime, to_int_huf

log = logging.getLogger(__name__)

_ROW_LINK = re.compile(r"\[(?P<title>.*?)\]\((?P<url>https?://[^)\s]+)\)")
_ID = re.compile(r"-(\d{6,})\.html")


def _features(title: str, description: str = "") -> dict:
    f = text.extract(title, description)
    rel, reason = text.relevance(title, f)
    keep = ["brand", "brand_basis", "object_type", "decor", "size_cm", "pieces", "condition",
            "damage_flags", "mark_flags", "suspect_flags"]
    out = {k: f[k] for k in keep}
    out["relevance"], out["reject_reason"] = rel, reason
    out["_canonical"] = f["canonical_en"]
    return out


def _price_record_from_listing(conn, lid: int, row: dict, observed: str, source_file: str,
                               price_type: str) -> None:
    db.upsert_price_record(conn, {
        "source": "vatera", "source_ref": row["source_id"], "market": "HU", "price_type": price_type,
        "amount": row["price_huf"], "currency": "HUF", "price_huf": row["price_huf"], "observed_at": observed,
        "title": row["title"], "description": row.get("description"), "brand": row["brand"],
        "object_type": row["object_type"], "decor": row["decor"], "size_cm": row["size_cm"],
        "pieces": row["pieces"], "condition": row["condition"], "url": row["url"], "listing_id": lid,
        "dedup_key": text.dedup_key(row["title"], None, row.get("seller")),
        "provenance": {"file": source_file, "note": "aktív hirdetés kínálati ára – nem eladási ár"}})


def _save_listing(conn, rec: dict, observed: str, origin: str) -> tuple[int, str]:
    feats = _features(rec["title"], rec.get("description") or "")
    canonical = feats.pop("_canonical")
    status, reason = "active", f"utolsó megfigyelés {observed[:10]} (import), azóta nem ellenőrzött"
    if rec.get("sale_type") == "aukcio" and rec.get("end_time") and rec["end_time"] < db.now_iso():
        status, reason = "ended", "az aukció lejárt; végeredmény nem ismert (nem bizonyított eladás)"
    if rec.get("availability") == "unavailable":
        status, reason = "ended", "a termékoldal nem elérhetőnek jelezte"
    fields = {**{k: v for k, v in rec.items() if k in db.LISTING_FIELDS}, **feats,
              "status": rec.get("status") or status, "status_reason": reason, "origin": origin,
              "extra": {"canonical_en": canonical, **rec.get("extra", {})}}
    if rec.get("relevance_override"):
        fields["relevance"], fields["reject_reason"] = rec["relevance_override"]
    lid, state = db.upsert_listing(conn, "vatera", rec["source_id"], fields, observed, via="import")
    if rec.get("checked"):
        conn.execute("UPDATE listings SET last_checked=? WHERE id=? AND (last_checked IS NULL OR last_checked<?)",
                     (observed, lid, observed))
    return lid, state


# --- riport markdown táblák (2026-09-16-i élő scrape) ---------------------------
def import_report_markdown(path: Path, conn=None, default_observed: str | None = None) -> dict:
    conn = conn or db.get_conn()
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    m = re.search(r"Készült:\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", content)
    observed = (parse_hu_datetime(f"{m.group(1)} {m.group(2)}") if m else default_observed) or db.now_iso()
    name = path.name
    sale_type = {"fix-aras.md": "fix", "alkukepes.md": "alku", "aukcio.md": "aukcio"}.get(name)
    rejected_file = name == "kiszurt.md"
    counts = {"rows": 0, "new": 0, "changed": 0, "unchanged": 0, "price_records": 0, "observed_at": observed}
    header: list[str] = []
    for line in content.splitlines():
        if line.startswith("| Hirdetés"):
            header = [h.strip() for h in line.strip("|").split("|")]
            continue
        if not line.startswith("| ") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        link = _ROW_LINK.search(cells[0])
        if not link:
            continue
        url = link.group("url")
        idm = _ID.search(url)
        if not idm:
            continue
        row = dict(zip(header, cells))
        title = link.group("title").replace("★", "").strip()
        rec = {"source_id": idm.group(1), "url": url, "title": title,
               "price_huf": to_int_huf(row.get("Ár")), "sale_type": sale_type,
               "extra": {"import_flags": row.get("Jelölések") or row.get("Kiszűrés oka")}}
        if sale_type == "aukcio":
            kind = (row.get("Ár típusa") or "").strip()
            rec["price_kind"] = kind
            rec["end_time"] = parse_hu_datetime(row.get("Vége"))
            if kind == "aktualis licit":
                rec["current_bid_huf"] = rec["price_huf"]
            else:
                rec["start_bid_huf"] = rec["price_huf"]
        else:
            rec["price_kind"] = "fix ar" if sale_type == "fix" else "iranyar"
        if rejected_file:
            rec["relevance_override"] = ("rejected", row.get("Kiszűrés oka") or "korábbi szűrés")
        lid, state = _save_listing(conn, rec, observed, f"import:riport/{name}")
        counts["rows"] += 1
        counts[state] += 1
        stored = dict(conn.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone())
        if stored["relevance"] == "accepted" and stored["price_huf"]:
            if sale_type in ("fix", "alku"):
                _price_record_from_listing(conn, lid, stored, observed, f"riport/{name}", "asking_active")
                counts["price_records"] += 1
            elif sale_type == "aukcio":
                ptype = "auction_current_bid" if rec.get("current_bid_huf") else "auction_start_price"
                _price_record_from_listing(conn, lid, stored, observed, f"riport/{name}", ptype)
                counts["price_records"] += 1
    conn.commit()
    log.info("%s: %s", name, counts)
    return counts


# --- részletes rekordok (decision-evidence.json, 2026-09-19) --------------------
def import_decision_evidence(path: Path, conn=None) -> dict:
    conn = conn or db.get_conn()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    counts = {"rows": 0, "new": 0, "changed": 0, "unchanged": 0}
    items = [c.get("fresh") | {"_fetched": c.get("fetched_at")} for c in data.get("previous_candidates", [])
             if c.get("fresh")]
    items += [c.get("record") | {"_fetched": data["screen"].get("checked_at")}
              for c in data.get("screen", {}).get("candidates", []) if c.get("record")]
    for r in items:
        if not r.get("listing_id") or text.detect_brand(r.get("title", ""))[0] is None:
            continue  # csak Herendi/Zsolnay
        observed = r["_fetched"] or db.now_iso()
        rec = {"source_id": r["listing_id"], "url": r["url"], "title": r["title"],
               "description": r.get("description"), "price_huf": r.get("price_huf"),
               "sale_type": r.get("sale_type"), "price_kind": r.get("price_kind"),
               "current_bid_huf": r.get("current_bid_huf"), "start_bid_huf": r.get("start_bid_huf"),
               "bid_count": r.get("bid_count"), "end_time": parse_hu_datetime(r.get("end_time")),
               "availability": r.get("availability"), "checked": True,
               "extra": {"availability": r.get("availability")}}
        lid, state = _save_listing(conn, rec, observed, f"import:{Path(path).name}")
        counts["rows"] += 1
        counts[state] += 1
        stored = dict(conn.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone())
        if stored["relevance"] == "accepted" and stored["sale_type"] in ("fix", "alku") and stored["price_huf"]:
            _price_record_from_listing(conn, lid, stored, observed, Path(path).name, "asking_active")
    conn.commit()
    return counts


# --- régi run.py kimenet (vatera_osszes.csv és társai) ---------------------------
def import_legacy_csv(path: Path, observed: str | None = None, conn=None) -> dict:
    """A `run.py` CSV-formátuma (storage.FIELDS). A megfigyelés ideje a mappanévből
    (run_YYYYMMDD_HHMMSS) vagy a fájl módosítási idejéből jön."""
    conn = conn or db.get_conn()
    path = Path(path)
    if observed is None:
        m = re.search(r"run_(\d{8})_(\d{6})", str(path))
        if m:
            dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
            observed = parse_hu_datetime(dt.isoformat())
        else:
            observed = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).replace(microsecond=0).isoformat()
    counts = {"rows": 0, "new": 0, "changed": 0, "unchanged": 0, "skipped": 0}
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            lid_raw = r.get("listing_id") or (_ID.search(r.get("url", "")) or [None, None])[1]
            if not lid_raw or not r.get("title"):
                counts["skipped"] += 1
                continue
            rec = {"source_id": str(lid_raw), "url": r["url"], "title": r["title"],
                   "description": r.get("description") or None, "price_huf": to_int_huf(r.get("price_huf")),
                   "sale_type": r.get("sale_type") or None, "price_kind": r.get("price_kind") or None,
                   "current_bid_huf": to_int_huf(r.get("current_bid_huf")),
                   "start_bid_huf": to_int_huf(r.get("start_bid_huf")),
                   "buy_now_huf": to_int_huf(r.get("buy_now_huf")),
                   "bid_count": int(r["bid_count"]) if (r.get("bid_count") or "").isdigit() else None,
                   "end_time": parse_hu_datetime(r.get("end_time")), "seller": r.get("seller") or None,
                   "availability": r.get("availability"), "checked": bool(r.get("description")),
                   "extra": {"legacy_reject_reason": r.get("reject_reason")}}
            if str(r.get("accepted", "")).lower() in ("false", "0"):
                rec["relevance_override"] = ("rejected", r.get("reject_reason") or "korábbi szűrés")
            lid, state = _save_listing(conn, rec, observed, f"import:{path.name}")
            counts["rows"] += 1
            counts[state] += 1
            stored = dict(conn.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone())
            if stored["relevance"] == "accepted" and stored["price_huf"]:
                if stored["sale_type"] in ("fix", "alku"):
                    _price_record_from_listing(conn, lid, stored, observed, path.name, "asking_active")
    conn.commit()
    return counts


# --- összehasonlító (US/EU) árak ------------------------------------------------
def import_picclick_comps(path: Path, observed: str = "2026-09-16T12:00:00+00:00", conn=None) -> dict:
    """elemzes/comps.json: PicClick-en keresztül látott AKTÍV eBay-hirdetések.

    A fájl csak mintát tárol (kulcsonként ≤7 cím + ár). A dátum a repó első
    commitjából becsült (a fájl nem tárolta a lekérés idejét)."""
    conn = conn or db.get_conn()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    n = 0
    for key, block in data.items():
        cur = block.get("cur", "USD")
        market = "US" if cur == "USD" else "EU"
        for sample in block.get("minta", []):
            price_s, _, title = sample.partition("|")
            try:
                amount = float(price_s.strip())
            except ValueError:
                continue
            title = re.sub(r"&#0?39;", "'", title.strip()).replace("&quot;", '"').replace("&amp;", "&")
            f = text.extract(title)
            if f["brand"] is None:
                continue
            ref = f"{key}:{text.dedup_key(title)}:{int(amount)}"
            db.upsert_price_record(conn, {
                "source": "picclick_ebay", "source_ref": ref, "market": market, "price_type": "asking_active",
                "amount": amount, "currency": cur, "price_huf": None, "observed_at": observed, "title": title,
                "brand": f["brand"], "object_type": f["object_type"], "decor": f["decor"],
                "size_cm": f["size_cm"], "pieces": f["pieces"], "condition": f["condition"],
                "url": block.get("url"), "dedup_key": text.dedup_key(title),
                "provenance": {"file": str(path), "query_key": key,
                               "note": "aktív eBay-hirdetés PicClick-kereséséből; minta, nem eladás"}})
            n += 1
    conn.commit()
    return {"price_records": n}


PRICE_CSV_COLUMNS = ["source", "source_ref", "market", "price_type", "amount", "currency", "observed_at",
                     "title", "description", "url", "buyer_premium_rate", "fees_note"]
VALID_PRICE_TYPES = {"realized_sale", "auction_hammer", "auction_final_bid", "asking_active",
                     "auction_current_bid", "auction_start_price"}


def import_price_csv(path: Path, conn=None) -> dict:
    """Általános ár-CSV (pl. aukciósházi leütési árak, eBay sold export, saját eladások).

    Kötelező oszlopok: source, source_ref, market (HU/US), price_type, amount,
    currency, observed_at (YYYY-MM-DD), title. Kitalált vagy becsült árat ne importálj.
    """
    conn = conn or db.get_conn()
    counts = {"rows": 0, "skipped": 0, "errors": []}
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in PRICE_CSV_COLUMNS[:8] if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Hiányzó oszlopok: {', '.join(missing)}")
        for i, r in enumerate(reader, 2):
            try:
                if r["price_type"] not in VALID_PRICE_TYPES:
                    raise ValueError(f"ismeretlen price_type: {r['price_type']}")
                if r["market"] not in ("HU", "US", "EU"):
                    raise ValueError(f"ismeretlen market: {r['market']}")
                amount = float(str(r["amount"]).replace(" ", "").replace(",", "."))
                observed = datetime.fromisoformat(r["observed_at"]).date().isoformat()
            except (ValueError, KeyError) as exc:
                counts["skipped"] += 1
                counts["errors"].append(f"{i}. sor: {exc}")
                continue
            f = text.extract(r["title"], r.get("description") or "")
            db.upsert_price_record(conn, {
                "source": r["source"], "source_ref": r["source_ref"], "market": r["market"],
                "price_type": r["price_type"], "amount": amount, "currency": r["currency"].upper(),
                "price_huf": amount if r["currency"].upper() == "HUF" else None,
                "buyer_premium_rate": float(r["buyer_premium_rate"]) if r.get("buyer_premium_rate") else None,
                "fees_note": r.get("fees_note"), "observed_at": observed, "title": r["title"],
                "description": r.get("description"), "brand": f["brand"], "object_type": f["object_type"],
                "decor": f["decor"], "size_cm": f["size_cm"], "pieces": f["pieces"], "condition": f["condition"],
                "url": r.get("url"), "dedup_key": text.dedup_key(r["title"]),
                "provenance": {"file": str(path), "row": i}})
            counts["rows"] += 1
    conn.commit()
    return counts


def import_ebay_api(conn=None, max_items_per_query: int = 1000) -> dict:
    """Hivatalos eBay Browse API – aktív amerikai kínálat (asking_active, US)."""
    from .sources.ebay import EbaySource
    conn = conn or db.get_conn()
    n = 0
    now = db.now_iso()
    for query, it in EbaySource().fetch_active(max_items_per_query):
        price = it.get("price") or {}
        title = it.get("title") or ""
        f = text.extract(title)
        if not f["brand"] or f["fake_hits"] or f["non_item_hits"]:
            continue
        db.upsert_price_record(conn, {
            "source": "ebay_browse", "source_ref": it.get("itemId"), "market": "US", "price_type": "asking_active",
            "amount": float(price.get("value", 0)), "currency": price.get("currency", "USD"), "observed_at": now,
            "title": title, "brand": f["brand"], "object_type": f["object_type"], "decor": f["decor"],
            "size_cm": f["size_cm"], "pieces": f["pieces"], "condition": f["condition"],
            "url": it.get("itemWebUrl"), "dedup_key": text.dedup_key(title),
            "provenance": {"query": query, "condition": it.get("condition"),
                           "image": (it.get("image") or {}).get("imageUrl")}})
        n += 1
    conn.commit()
    return {"price_records": n}


def import_repo_snapshot(conn=None) -> dict:
    """A repóban lévő összes valós adat importja (a 2026-09-16/19-i élő futásokból)."""
    conn = conn or db.get_conn()
    root = settings.ROOT
    out = {}
    observed = None
    for name in ("fix-aras.md", "alkukepes.md", "aukcio.md", "kiszurt.md"):
        p = root / "riport" / name
        if p.exists():
            # a kiszurt.md ugyanabból a futásból készült, de nem írja ki az időpontot
            out[name] = import_report_markdown(p, conn, default_observed=observed)
            observed = observed or out[name]["observed_at"]
    p = root / "riport" / "decision-evidence.json"
    if p.exists():
        out["decision-evidence.json"] = import_decision_evidence(p, conn)
    p = root / "elemzes" / "comps.json"
    if p.exists():
        out["comps.json"] = import_picclick_comps(p, conn=conn)
    db.set_meta(conn, "last_import", {"at": db.now_iso(), "result": out})
    return out
