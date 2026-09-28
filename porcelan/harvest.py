"""Tömeges, folytatható adatgyűjtés a hivatalos eBay Browse API-ból – képekkel.

Cél: több tízezer / százezer (kép, ár, leírás) pár a képalapú árbecslés
előtanításához (általános porcelán/kerámia korpusz) és finomhangolásához
(Herendi/Zsolnay korpusz).

Az API egy lekérdezésre legfeljebb 10 000 találatot lapoz végig. Ezért minden
(lekérdezés, kategória) párt ársávokra bontunk; ha egy sáv jelzett találatszáma
a korlát felett van, a sávot mértani középnél kettévágjuk (adaptív felbontás),
amíg minden szelet végigjárható. Az állapot a `harvest_slices` táblában van:
megszakítás vagy napi kvóta (HTTP 429) után a következő futás folytatja.

Az eBay aktív hirdetései KÍNÁLATI árak (`asking_active`). Eladott tételek árát
a Browse API nem adja; azok CSV-importtal kerülnek be (docs/ADATFORRASOK.md).
"""
from __future__ import annotations

import base64
import logging
import math
import os
import time

import requests

from . import db, settings, text

log = logging.getLogger(__name__)
TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
PAGE = 200
MAX_WINDOW = 10_000          # az API offset+limit felső korlátja
SPLIT_ABOVE = 9_600          # e fölött a szelet kettévágandó
MIN_WIDTH_USD = 0.5          # ennél keskenyebb ársávot már nem vágunk (a maradék nem gyűjthető be teljesen)
BROKEN_CONDITIONS = {"7000"}  # For parts or not working


class QuotaExceeded(RuntimeError):
    pass


class EbayHarvester:
    def __init__(self, conn=None, session=None, sleep: float | None = None, progress=None):
        self.conn = conn or db.get_conn()
        self.session = session or requests.Session()
        self.cfg = settings.get("ebay_harvest")
        self.sleep = self.cfg["min_delay_sec"] if sleep is None else sleep
        self.progress = progress or (lambda f, m: log.info(m))
        self._token = None
        self._token_exp = 0.0
        self.stats = {"calls": 0, "items": 0, "new_records": 0, "skipped_brand_fake": 0, "images_queued": 0,
                      "slices_split": 0, "slices_done": 0, "truncated_slices": 0}

    # -- auth ---------------------------------------------------------------
    def _auth_header(self) -> dict:
        if not (os.environ.get("EBAY_CLIENT_ID") and os.environ.get("EBAY_CLIENT_SECRET")):
            raise RuntimeError("Nincs EBAY_CLIENT_ID / EBAY_CLIENT_SECRET a környezetben "
                               "(ingyenes kulcs: developer.ebay.com).")
        if not self._token or time.time() > self._token_exp - 60:
            cred = f"{os.environ['EBAY_CLIENT_ID']}:{os.environ['EBAY_CLIENT_SECRET']}".encode()
            r = self.session.post(TOKEN_URL, timeout=30, headers={
                "Authorization": "Basic " + base64.b64encode(cred).decode(),
                "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"})
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            self._token_exp = time.time() + float(data.get("expires_in", 7200))
        return {"Authorization": f"Bearer {self._token}",
                "X-EBAY-C-MARKETPLACE-ID": self.cfg["marketplace"]}

    # -- szeletek -------------------------------------------------------------
    def seed(self) -> int:
        n = 0
        lo, hi = self.cfg["price_min_usd"], self.cfg["price_max_usd"]
        for corpus, block in (("herend_zsolnay", self.cfg["queries_herend_zsolnay"]),
                              ("general", self.cfg["queries_general"])):
            for q in block:
                cats = self.cfg.get("category_ids") or [""]
                for cat in cats:
                    cur = self.conn.execute(
                        "INSERT OR IGNORE INTO harvest_slices(source, corpus, query, category, price_lo, price_hi, "
                        "updated_at) VALUES('ebay', ?, ?, ?, ?, ?, ?)", (corpus, q, cat, lo, hi, db.now_iso()))
                    n += cur.rowcount
        self.conn.commit()
        return n

    def _search(self, sl, offset: int, limit: int) -> dict:
        params = {"q": sl["query"], "limit": limit, "offset": offset,
                  "filter": f"price:[{sl['price_lo']:.2f}..{sl['price_hi']:.2f}],priceCurrency:USD,"
                            f"buyingOptions:{{FIXED_PRICE|BEST_OFFER|AUCTION}}"}
        if sl["category"]:
            params["category_ids"] = sl["category"]
        for attempt in range(4):
            if self.stats["calls"] >= self.cfg["max_calls_per_run"]:
                raise QuotaExceeded("a futásonkénti híváskeret elérve")
            self.stats["calls"] += 1
            try:
                r = self.session.get(SEARCH_URL, headers=self._auth_header(), params=params, timeout=40)
            except requests.RequestException as exc:
                log.warning("eBay hálózati hiba: %s", exc)
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429:
                raise QuotaExceeded("eBay napi híváskvóta elérve (HTTP 429)")
            if r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            r.raise_for_status()
            if self.sleep:
                time.sleep(self.sleep)
            return r.json()
        raise RuntimeError("eBay keresés tartósan sikertelen")

    def _split(self, sl, total: int) -> None:
        lo, hi = sl["price_lo"], sl["price_hi"]
        mid = round(math.sqrt(max(lo, 0.01) * hi), 2)
        if mid <= lo or mid >= hi:
            mid = round((lo + hi) / 2, 2)
        for a, b in ((lo, mid), (mid + 0.01, hi)):
            self.conn.execute("INSERT OR IGNORE INTO harvest_slices(source, corpus, query, category, price_lo, "
                              "price_hi, updated_at) VALUES('ebay',?,?,?,?,?,?)",
                              (sl["corpus"], sl["query"], sl["category"], a, b, db.now_iso()))
        self.conn.execute("UPDATE harvest_slices SET status='split', reported_total=?, updated_at=? WHERE id=?",
                          (total, db.now_iso(), sl["id"]))
        self.stats["slices_split"] += 1

    # -- tételek --------------------------------------------------------------
    def _store(self, sl, item: dict) -> None:
        self.stats["items"] += 1
        title = item.get("title") or ""
        price = item.get("price") or {}
        try:
            amount = float(price.get("value"))
        except (TypeError, ValueError):
            return
        if (price.get("currency") or "USD") != "USD" or amount <= 0:
            return
        f = text.extract(title, item.get("shortDescription") or "")
        if f["fake_hits"] or f["non_item_hits"]:
            self.stats["skipped_brand_fake"] += 1
            return
        corpus = "herend_zsolnay" if f["brand"] else "general"
        if sl["corpus"] == "herend_zsolnay" and not f["brand"]:
            corpus = "general"          # márkás keresés márka nélküli találata: általános korpusz
        cond = f["condition"]
        if str(item.get("conditionId")) in BROKEN_CONDITIONS:
            cond = "serult"
        images = [(item.get("image") or {}).get("imageUrl")]
        images += [x.get("imageUrl") for x in (item.get("additionalImages") or [])]
        images = [u for u in images if u][: self.cfg["max_images_per_item"]]
        cats = item.get("categories") or []
        existing = self.conn.execute("SELECT id FROM price_records WHERE source='ebay_browse' AND source_ref=? "
                                     "AND price_type='asking_active' AND market='US'", (item.get("itemId"),)).fetchone()
        rid = db.upsert_price_record(self.conn, {
            "source": "ebay_browse", "source_ref": item.get("itemId"), "market": "US",
            "price_type": "asking_active", "amount": amount, "currency": "USD", "observed_at": db.now_iso(),
            "title": title, "description": item.get("shortDescription"), "brand": f["brand"],
            "object_type": f["object_type"], "decor": f["decor"], "size_cm": f["size_cm"], "pieces": f["pieces"],
            "condition": cond, "url": item.get("itemWebUrl"), "dedup_key": text.dedup_key(
                title, None, (item.get("seller") or {}).get("username")),
            "corpus": corpus, "image_url": images[0] if images else None,
            "provenance": {"query": sl["query"], "category": sl["category"], "slice": sl["id"],
                           "ebay_condition": item.get("condition"), "condition_id": item.get("conditionId"),
                           "categories": [c.get("categoryName") for c in cats][:3],
                           "buying_options": item.get("buyingOptions"),
                           "note": "aktív eBay-hirdetés kínálati ára (Browse API) – nem eladási ár"}})
        if not existing:
            self.stats["new_records"] += 1
        for pos, u in enumerate(images):
            cur = self.conn.execute("INSERT OR IGNORE INTO images(price_record_id, url, position) VALUES(?,?,?)",
                                    (rid, u, pos))
            self.stats["images_queued"] += cur.rowcount

    def _run_slice(self, sl) -> None:
        offset = sl["next_offset"] or 0
        while True:
            data = self._search(sl, offset, PAGE)
            total = int(data.get("total") or 0)
            if offset == 0 and total > SPLIT_ABOVE and (sl["price_hi"] - sl["price_lo"]) > MIN_WIDTH_USD:
                self._split(sl, total)
                return
            for it in data.get("itemSummaries") or []:
                self._store(sl, it)
            got = len(data.get("itemSummaries") or [])
            offset += got
            limit_reached = offset + PAGE > MAX_WINDOW
            done = got == 0 or offset >= total or not data.get("next") or limit_reached
            msg = None
            if limit_reached and offset < total:
                msg = f"csonkolt szelet: {offset}/{total} (az API 10 000-es korlátja)"
                self.stats["truncated_slices"] += 1
            self.conn.execute("UPDATE harvest_slices SET reported_total=?, fetched=?, next_offset=?, status=?, "
                              "message=?, updated_at=? WHERE id=?",
                              (total, offset, offset, "done" if done else "pending", msg, db.now_iso(), sl["id"]))
            self.conn.commit()
            if done:
                self.stats["slices_done"] += 1
                return

    def run(self, max_items: int | None = None) -> dict:
        self.seed()
        status, message = "completed", ""
        try:
            while True:
                if max_items and self.stats["items"] >= max_items:
                    status, message = "interrupted", "tételkeret elérve; a következő futás folytatja"
                    break
                sl = self.conn.execute("SELECT * FROM harvest_slices WHERE source='ebay' AND status='pending' "
                                       "ORDER BY corpus='general', id LIMIT 1").fetchone()
                if sl is None:
                    break
                self._run_slice(sl)
                self._report()
        except QuotaExceeded as exc:
            status, message = "interrupted", f"{exc}; a következő futás folytatja"
        except KeyboardInterrupt:
            status, message = "interrupted", "megszakítva; a következő futás folytatja"
        self.conn.commit()
        summary = harvest_summary(self.conn)
        db.set_meta(self.conn, "last_harvest_ebay", {"at": db.now_iso(), "status": status, "message": message,
                                                     "stats": self.stats, "summary": summary})
        return {"status": status, "message": message, "stats": self.stats, "summary": summary}

    def _report(self):
        s = harvest_summary(self.conn)
        frac = s["slices_done"] / max(1, s["slices_done"] + s["slices_pending"])
        self.progress(frac, f"eBay: {self.stats['items']} tétel ebben a futásban, {s['slices_done']} kész / "
                            f"{s['slices_pending']} függő szelet")


def harvest_summary(conn) -> dict:
    r = conn.execute("SELECT SUM(status='done') d, SUM(status='pending') p, SUM(status='split') s, "
                     "SUM(CASE WHEN status='done' THEN reported_total ELSE 0 END) rt, "
                     "SUM(CASE WHEN status='done' THEN fetched ELSE 0 END) f, "
                     "SUM(message LIKE 'csonkolt%') t FROM harvest_slices WHERE source='ebay'").fetchone()
    reported, fetched = r["rt"] or 0, r["f"] or 0
    return {"slices_done": r["d"] or 0, "slices_pending": r["p"] or 0, "slices_split": r["s"] or 0,
            "reported_total_done": reported, "fetched_done": fetched, "truncated_slices": r["t"] or 0,
            "coverage": round(fetched / reported, 3) if reported else None,
            "complete": (r["p"] or 0) == 0 and (r["t"] or 0) == 0 and (r["d"] or 0) > 0}
