"""Dashboard backend (FastAPI).

Indítás:  python -m porcelan serve  →  http://127.0.0.1:8000
Induláskor betölti a `models/CURRENT` modellverziót (újratanítás nélkül).
Helyi használatra készült: alapból csak 127.0.0.1-en figyel, nincs felhasználókezelés.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import costs, db, jobs, ranking, settings
from .predict import ModelMissing, get_estimator, load_manifest
from .scoring import load_estimate

log = logging.getLogger(__name__)
WEB = settings.ROOT / "web"
STALE_CRAWL_HOURS = 48
_state: dict = {"estimator": None, "model_error": None}
_cache: dict = {}
_cache_lock = threading.Lock()


def _load_model():
    try:
        _state["estimator"] = get_estimator(reload=True)
        _state["model_error"] = None
    except ModelMissing as exc:
        _state["estimator"], _state["model_error"] = None, str(exc)
    except Exception as exc:  # sérült modellfájl: érthető állapotjelzés
        log.exception("Modell betöltési hiba")
        _state["estimator"], _state["model_error"] = None, f"Modell betöltési hiba: {exc}"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.get_conn()
    jobs.reap_dead()
    _load_model()
    # gyorsítótár előmelegítése, hogy az első dashboard-lekérés is gyors legyen
    threading.Thread(target=lambda: _assessed({}), daemon=True).start()
    yield


app = FastAPI(title="Herendi–Zsolnay vételkereső", lifespan=lifespan)


def _hours_since(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600
    except ValueError:
        return None


# ---------------------------------------------------------------------------
def _ensure_current():
    """Új modellverzió (pl. háttértanítás után) automatikus betöltése."""
    from .predict import current_version
    v = current_version()
    est = _state["estimator"]
    if v and (est is None or est.version != v):
        _load_model()


@app.get("/api/status")
def status():
    conn = db.get_conn()
    _ensure_current()
    est = _state["estimator"]
    man = est.manifest if est else load_manifest()
    model = None
    if man:
        chosen = man["chosen_model"]
        test = man["metrics"]["test"]
        model = {"version": man["version"], "status": man["status"], "reasons": man["status_reasons"],
                 "created_at": man["created_at"], "chosen": chosen, "basis": man["target_basis"],
                 "loaded": est is not None, "rows": man["dataset"].get("rows"),
                 "test": {m: test.get(f"{n}/{m}") for m, n in chosen.items()},
                 "baseline": {m: test.get(f"baseline_group_median/{m}") for m in chosen}}
    runs = {}
    for r in conn.execute("SELECT * FROM crawl_runs WHERE id IN (SELECT MAX(id) FROM crawl_runs GROUP BY source)"):
        st = json.loads(r["stats"] or "{}")
        runs[r["source"]] = {"id": r["id"], "status": r["status"], "started_at": r["started_at"],
                             "finished_at": r["finished_at"], "message": r["message"],
                             "coverage": (st.get("coverage") or {}).get("label"),
                             "coverage_detail": {k: (st.get("coverage") or {}).get(k) for k in
                                                 ("scopes", "scopes_exhausted", "reported_total_sum", "seen_sum",
                                                  "pending_tasks", "failed_tasks")}}
    last_ok = conn.execute("SELECT source, finished_at FROM crawl_runs WHERE status='completed' "
                           "ORDER BY finished_at DESC LIMIT 1").fetchone()
    counts = {f"{r['source']}/{r['status']}": r["n"] for r in conn.execute(
        "SELECT source, status, COUNT(*) n FROM listings WHERE relevance='accepted' GROUP BY 1,2")}
    newest = conn.execute("SELECT MAX(COALESCE(last_checked, last_seen)) t FROM listings").fetchone()["t"]
    warnings = []
    if not man:
        warnings.append("Nincs betanított modell: futtasd a tanítást (Tanítás gomb vagy `python -m porcelan train`).")
    elif man["status"] != "validált":
        warnings.append("A modell KÍSÉRLETI: " + "; ".join(man["status_reasons"][:3]))
    if _state["model_error"] and man:
        warnings.append(_state["model_error"])
    age = _hours_since(newest)
    if age is None:
        warnings.append("Nincs adat: indíts adatgyűjtést vagy importálj CSV-t.")
    elif age > STALE_CRAWL_HOURS:
        warnings.append(f"Régi adat: a legfrissebb ellenőrzés {age / 24:.0f} napja volt. Az árak és az elérhetőség "
                        f"azóta változhatott.")
    for src, r in runs.items():
        if r["status"] in ("blocked", "failed"):
            warnings.append(f"{src}: a legutóbbi adatgyűjtés sikertelen ({r['status']}): {r['message'] or ''}")
        elif r["status"] == "interrupted":
            warnings.append(f"{src}: a legutóbbi adatgyűjtés megszakadt; a következő indítás folytatja.")
    job_rows = [dict(r) for r in conn.execute("SELECT id, kind, status, progress, message, created_at, started_at, "
                                              "finished_at FROM jobs ORDER BY id DESC LIMIT 8")]
    from .volume import data_volume
    vol = data_volume(conn)
    hz_img = next(g for g in vol["goals"] if g["key"] == "hz_records_with_images")
    if hz_img["have"] < hz_img["target"]:
        warnings.append(f"Kevés képes tanítóadat: {hz_img['have']} / {hz_img['target']} Herendi/Zsolnay kép+ár pár. "
                        f"A képalapú becsléshez sok tízezer képes adat kell (eBay-gyűjtés, Vatera-bejárás).")
    return {"model": model, "model_error": _state["model_error"], "crawl": runs, "volume": vol["goals"],
            "pending_image_downloads": vol["pending_image_downloads"],
            "last_successful_crawl": dict(last_ok) if last_ok else None,
            "last_import": db.get_meta(conn, "last_import"), "last_scoring": db.get_meta(conn, "last_scoring"),
            "newest_observation": newest, "counts": counts, "warnings": warnings, "jobs": job_rows,
            "clip_ready": __import__("porcelan.vision", fromlist=["available"]).available()}


@app.get("/api/assumptions")
def get_assumptions():
    return costs.assumptions()


def _overrides(request: Request) -> dict:
    out = {}
    for k, v in request.query_params.items():
        if k.startswith("a."):
            try:
                out[k[2:]] = float(v)
            except ValueError:
                raise HTTPException(400, f"Érvénytelen szám: {k}")
    return out


def _assessed(overrides: dict) -> list[dict]:
    """Minden aktív, becsült hirdetés értékelése (rövid gyorsítótárral)."""
    est = _state["estimator"]
    if est is None:
        return []
    conn = db.get_conn()
    stamp = conn.execute("SELECT COUNT(*) || '|' || COALESCE(MAX(created_at),'') FROM estimates WHERE model_version=?",
                         (est.version,)).fetchone()[0]
    stamp += "|" + str(conn.execute("SELECT MAX(last_seen) || MAX(COALESCE(last_checked,'')) FROM listings").fetchone()[0])
    key = (est.version, stamp, json.dumps(overrides, sort_keys=True))
    with _cache_lock:
        hit = _cache.get("assessed")
        if hit and hit[0] == key and time.time() - hit[1] < 60:
            return hit[2]
    a = costs.assumptions(overrides)
    rows = conn.execute("SELECT l.*, e.payload, e.input_hash, e.created_at AS estimated_at FROM listings l "
                        "JOIN estimates e ON e.listing_id=l.id AND e.model_version=? "
                        "WHERE l.relevance='accepted' AND l.status='active'", (est.version,)).fetchall()
    first_img = {r["listing_id"]: r for r in conn.execute(
        "SELECT i.listing_id, i.url, COALESCE(o.path, i.path) path FROM images i LEFT JOIN images o ON o.id=i.dup_of "
        "WHERE i.id IN (SELECT MIN(id) FROM images GROUP BY listing_id)")}
    out = []
    for r in rows:
        listing = dict(r)
        payload = json.loads(listing.pop("payload"))
        res = ranking.assess(listing, payload, a)
        img = first_img.get(r["id"])
        out.append({"listing": listing, "assessment": res, "features": payload.get("features", {}),
                    "model_version": payload.get("model_version"), "input_hash": r["input_hash"],
                    "image": (f"/images/{img['path']}" if img and img["path"] else (img["url"] if img else None))})
    with _cache_lock:
        _cache["assessed"] = (key, time.time(), out)
    return out


def _card(item: dict, market: str) -> dict:
    l, res = item["listing"], item["assessment"]
    m = res["markets"].get(market, {})
    other = res["markets"].get("US" if market == "HU" else "HU", {})
    return {
        "id": l["id"], "source": l["source"], "url": l["url"], "title": l["title"], "image": item["image"],
        "price_huf": l["price_huf"], "sale_type": l["sale_type"], "bid_count": l["bid_count"],
        "end_time": l["end_time"], "brand": l["brand"], "condition": l["condition"],
        "last_checked": l["last_checked"] or l["last_seen"], "status": l["status"],
        "hu": _market_summary(res["markets"].get("HU")), "us": _market_summary(res["markets"].get("US")),
        "market": market, "recommended": m.get("recommended", False), "candidate": m.get("candidate", False), "below_value": m.get("below_value", False),
        "profitable": m.get("profitable", False),
        "other_market_flags": {"below_value": other.get("below_value"), "profitable": other.get("profitable")},
        "reason": m.get("reason"), "risks": m.get("risks", [])[:4], "abstain": m.get("abstain_reasons", []),
        "score": m.get("score", 0), "model_version": item["model_version"],
    }


def _market_summary(m: dict | None) -> dict | None:
    if not m:
        return None
    return {"value_huf": m["value_huf"], "value_native": m["value_native"], "currency": m["currency"],
            "expected_sale_huf": m["expected_sale_huf"], "confidence": m["confidence"], "basis": m["basis"],
            "discount_pct": m.get("discount_pct"), "profit_huf": (m.get("base") or {}).get("profit_huf"),
            "roi_pct": (m.get("base") or {}).get("roi_pct"),
            "conservative_profit_huf": (m.get("conservative") or {}).get("profit_huf"),
            "conservative_roi_pct": (m.get("conservative") or {}).get("roi_pct"),
            "max_bid_huf": m.get("max_bid_huf"), "below_value": m.get("below_value"),
            "profitable": m.get("profitable"), "recommended": m.get("recommended")}


SORTS = {
    "score": lambda c: -(c["score"] or 0),
    "profit": lambda c: -((c["_m"] or {}).get("conservative_profit_huf") or -1e12),
    "roi": lambda c: -((c["_m"] or {}).get("conservative_roi_pct") or -1e12),
    "discount": lambda c: -((c["_m"] or {}).get("discount_pct") or -1e12),
    "confidence": lambda c: -((c["_m"] or {}).get("confidence") or 0),
    "price_asc": lambda c: c["price_huf"] or 0,
    "price_desc": lambda c: -(c["price_huf"] or 0),
    "checked": lambda c: "" if not c["last_checked"] else "".join(chr(255 - ord(x)) for x in c["last_checked"]),
}


@app.get("/api/deals")
def deals(request: Request, market: str = Query("HU", pattern="^(HU|US)$"), brand: str | None = None,
          max_price: int | None = Query(None, ge=0), min_price: int | None = Query(None, ge=0),
          min_discount: float | None = None, min_profit: int | None = None,
          min_confidence: float | None = Query(None, ge=0, le=1), source: str | None = None,
          sale_type: str | None = None, only_recommended: bool = False, only_candidates: bool = False, include_abstain: bool = True,
          sort: str = "score", limit: int = Query(60, ge=1, le=500), offset: int = Query(0, ge=0)):
    if _state["estimator"] is None:
        return {"total": 0, "items": [], "error": _state["model_error"] or "Nincs betöltött modell."}
    items = _assessed(_overrides(request))
    types = set(sale_type.split(",")) if sale_type else None
    cards = []
    for it in items:
        c = _card(it, market)
        m = c["hu"] if market == "HU" else c["us"]
        c["_m"] = m
        if brand and c["brand"] != brand:
            continue
        if source and c["source"] != source:
            continue
        if types and c["sale_type"] not in types:
            continue
        if max_price is not None and (c["price_huf"] or 0) > max_price:
            continue
        if min_price is not None and (c["price_huf"] or 0) < min_price:
            continue
        if m is None:
            continue
        if min_discount is not None and (m.get("discount_pct") is None or m["discount_pct"] < min_discount):
            continue
        if min_profit is not None and (m.get("conservative_profit_huf") is None or m["conservative_profit_huf"] < min_profit):
            continue
        if min_confidence is not None and m["confidence"] < min_confidence:
            continue
        if only_recommended and not c["recommended"]:
            continue
        if only_candidates and not (c["recommended"] or c["candidate"]):
            continue
        if not include_abstain and c["abstain"]:
            continue
        cards.append(c)
    cards.sort(key=SORTS.get(sort, SORTS["score"]))
    for c in cards:
        c.pop("_m", None)
    summary = {"recommended": sum(c["recommended"] for c in cards), "candidate": sum(c["candidate"] for c in cards),
               "below_value": sum(bool(c["below_value"]) for c in cards),
               "profitable": sum(bool(c["profitable"]) for c in cards)}
    return {"total": len(cards), "summary": summary, "items": cards[offset:offset + limit],
            "model_version": _state["estimator"].version,
            "model_status": _state["estimator"].manifest["status"]}


@app.get("/api/listings/{listing_id}")
def listing_detail(listing_id: int, request: Request):
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM listings WHERE id=?", (listing_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Nincs ilyen hirdetés")
    listing = dict(row)
    listing["extra"] = json.loads(listing["extra"]) if listing["extra"] else {}
    imgs = []
    from .images import listing_images
    for im in listing_images(conn, listing_id):
        imgs.append({"src": f"/images/{im['local']}" if im["local"] else im["url"], "remote": im["url"],
                     "status": im["status"]})
    history = [dict(r) for r in conn.execute("SELECT observed_at, price_huf, current_bid_huf, bid_count, status, via "
                                             "FROM observations WHERE listing_id=? ORDER BY observed_at", (listing_id,))]
    est = _state["estimator"]
    estimate, assessment = None, None
    if est is not None:
        estimate = load_estimate(conn, listing_id, est.version)
        if estimate is None and listing["relevance"] == "accepted":
            estimate = est.predict([listing], conn)[0]      # betöltött súlyokkal, újratanítás nélkül
            estimate["estimated_at"] = db.now_iso()
            estimate["input_hash"] = "on-demand"
        if estimate:
            assessment = ranking.assess(listing, estimate, costs.assumptions(_overrides(request)))
    return {"listing": listing, "images": imgs, "history": history, "estimate": estimate,
            "assessment": assessment, "assumptions": costs.assumptions(_overrides(request)),
            "model": {"version": est.version, "status": est.manifest["status"],
                      "basis": est.manifest["target_basis"]} if est else None}


@app.get("/api/coverage")
def coverage_detail():
    conn = db.get_conn()
    out = {}
    for r in conn.execute("SELECT * FROM crawl_runs WHERE id IN (SELECT MAX(id) FROM crawl_runs GROUP BY source)"):
        st = json.loads(r["stats"] or "{}")
        out[r["source"]] = {"run": dict(r) | {"stats": None}, "stats": {k: v for k, v in st.items() if k != "coverage"},
                            "coverage": st.get("coverage")}
    return out


@app.get("/api/model")
def model_info():
    man = load_manifest()
    if not man:
        raise HTTPException(404, "Nincs modell")
    return man


@app.post("/api/model/reload")
def model_reload():
    _load_model()
    return {"loaded": _state["estimator"] is not None, "error": _state["model_error"]}


@app.get("/api/jobs")
def list_jobs():
    return [dict(r) for r in db.get_conn().execute("SELECT * FROM jobs ORDER BY id DESC LIMIT 30")]


@app.post("/api/jobs")
async def start_job(request: Request):
    body = await request.json()
    kind = body.get("kind")
    params = body.get("params") or {}
    if kind not in jobs.KINDS or kind == "import_csv":
        raise HTTPException(400, "Ismeretlen vagy nem így indítható feladat")
    try:
        jid = jobs.create(kind, params)
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    jobs.spawn(jid)
    return {"id": jid}


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: int):
    return {"cancelled": jobs.cancel(job_id)}


@app.post("/api/import")
async def import_csv(file: UploadFile = File(...), type: str = Query("listings", pattern="^(listings|prices)$")):
    name = re.sub(r"[^\w.\-]", "_", Path(file.filename or "upload.csv").name)
    if not name.lower().endswith(".csv"):
        raise HTTPException(400, "Csak .csv fájl importálható")
    dest_dir = settings.path("data_dir") / "uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{datetime.now():%Y%m%d_%H%M%S}_{name}"
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(413, "Túl nagy fájl")
    dest.write_bytes(data)
    try:
        jid = jobs.create("import_csv", {"path": str(dest), "type": type})
    except RuntimeError as exc:
        raise HTTPException(409, str(exc))
    jobs.spawn(jid)
    return {"id": jid, "saved": dest.name}


@app.get("/images/{path:path}")
def image(path: str):
    base = settings.path("image_dir").resolve()
    p = (base / path).resolve()
    if base not in p.parents or not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, headers={"Cache-Control": "public, max-age=604800"})


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("API hiba")
    return JSONResponse({"error": f"Belső hiba: {exc}"}, status_code=500)
