"""Folytatható, inkrementális bejárás egy forráson.

Frontier (SQLite): keresési/kategória/termékoldal feladatok prioritással.
Megszakítás (Ctrl+C, SIGTERM, időkeret, kéréskeret) után a következő futás a
félbemaradt bejárást folytatja. Blokkolásnál (403/429/CAPTCHA) a futás
`blocked` állapotban leáll – nem kerüljük meg.

Státuszok:
  active       a legutóbbi ellenőrzéskor elérhető
  ended        lejárt / nem elérhető, eladás nem bizonyított
  sold         a forrás elkeltként jelzi, vagy aukció licittel zárult
  disappeared  N teljes bejárásban nem láttuk – NEM eladás
  removed      a termékoldal 404/410
"""
from __future__ import annotations

import hashlib
import json
import logging
import signal
import time
from datetime import datetime, timedelta, timezone

from . import db, settings, text
from .net import BlockedError, DisallowedError, Fetcher, NetworkError
from .sources import Card, Source, Task, get_source

log = logging.getLogger(__name__)

# A sorrend: lezárult aukció végeredménye, majd a márkás termékoldalak (ezek hozzák
# az árat), és csak utána a kategóriák széles bejárása. Ha a kategóriák mennének
# előbb, egy nagy kategóriafán a termékoldalak órákig nem indulnának el.
PRI_ENDED_AUCTION, PRI_DETAIL, PRI_CATEGORY, PRI_FULL = 5, 10, 20, 90


class _Stop(Exception):
    pass


def _now() -> str:
    return db.now_iso()


def _features_to_fields(feats: dict) -> dict:
    keys = ["brand", "brand_basis", "object_type", "decor", "size_cm", "pieces", "condition",
            "damage_flags", "mark_flags", "suspect_flags"]
    return {k: feats.get(k) for k in keys}


class Crawler:
    def __init__(self, source: Source | str, conn=None, fetcher: Fetcher | None = None,
                 full_catalog: bool | None = None, max_requests: int | None = None,
                 time_budget_sec: float | None = None, progress=None, corpus: str = "relevant"):
        self.source = get_source(source) if isinstance(source, str) else source
        if corpus not in ("relevant", "general"):
            raise ValueError("corpus: relevant | general")
        self.corpus = corpus
        self.conn = conn or db.get_conn()
        self.fetcher = fetcher or Fetcher()
        self.cfg = settings.get("crawl")
        self.full_catalog = self.cfg["full_catalog"] if full_catalog is None else full_catalog
        self.max_requests = max_requests
        self.deadline = time.monotonic() + time_budget_sec if time_budget_sec else None
        self.progress = progress or (lambda frac, msg: None)
        self.stats = {"index_pages": 0, "detail_pages": 0, "cards": 0, "new": 0, "changed": 0,
                      "unchanged": 0, "details_skipped_fresh": 0, "errors": 0, "blocked": 0,
                      "disallowed": 0, "sold": 0, "ended": 0, "removed": 0, "disappeared": 0}
        self._stop_requested = False
        self._scope_seen: dict[str, set] = {}

    # -- run lifecycle --------------------------------------------------------
    def _open_run(self, resume: bool) -> tuple[int, bool]:
        c = self.conn
        if resume:
            row = c.execute("SELECT id FROM crawl_runs WHERE source=? AND status IN ('running','interrupted','failed','blocked') "
                            "ORDER BY id DESC LIMIT 1", (self.source.name,)).fetchone()
            if row:
                c.execute("UPDATE crawl_runs SET status='running', message='folytatva' WHERE id=?", (row["id"],))
                c.execute("UPDATE frontier SET status='pending' WHERE run_id=? AND status='in_progress'", (row["id"],))
                c.commit()
                return row["id"], True
        cur = c.execute("INSERT INTO crawl_runs(source, mode, started_at, status) VALUES(?,?,?, 'running')",
                        (self.source.name, "full" if self.full_catalog else self.corpus, _now()))
        run_id = cur.lastrowid
        seeds = (self.source.general_tasks() if self.corpus == "general" and hasattr(self.source, "general_tasks")
                 else self.source.seed_tasks(self.full_catalog))
        for t in seeds:
            self._enqueue(run_id, t)
        # Lejárt, de még aktívnak tárolt aukciók: végeredmény ellenőrzése.
        for row in c.execute("SELECT url FROM listings WHERE source=? AND status='active' AND sale_type='aukcio' "
                             "AND end_time IS NOT NULL AND end_time < ?", (self.source.name, _now())).fetchall():
            self._enqueue(run_id, Task("detail", row["url"], None, 1, PRI_ENDED_AUCTION))
        c.commit()
        return run_id, False

    def _enqueue(self, run_id: int, t: Task) -> None:
        self.conn.execute("INSERT OR IGNORE INTO frontier(run_id, source, kind, url, query, page, priority, "
                          "updated_at) VALUES(?,?,?,?,?,?,?,?)",
                          (run_id, self.source.name, t.kind, t.url, t.query, t.page, t.priority, _now()))

    def request_stop(self, *_):
        self._stop_requested = True

    def _check_budget(self, used: int):
        if self._stop_requested:
            raise _Stop("leállítás kérve")
        if self.max_requests is not None and used >= self.max_requests:
            raise _Stop("kéréskeret elérve")
        if self.deadline and time.monotonic() > self.deadline:
            raise _Stop("időkeret elérve")

    def run(self, resume: bool = True) -> dict:
        run_id, resumed = self._open_run(resume)
        self.run_id = run_id
        log.info("Bejárás #%d (%s, %s)%s", run_id, self.source.name,
                 "teljes katalógus" if self.full_catalog else "releváns", " – folytatás" if resumed else "")
        old_handler = None
        try:
            old_handler = signal.signal(signal.SIGTERM, self.request_stop)
        except ValueError:  # nem fő szál
            pass
        status, message = "completed", ""
        used = 0
        net_failures = 0
        try:
            while True:
                self._check_budget(used)
                task = self.conn.execute("SELECT * FROM frontier WHERE run_id=? AND status='pending' "
                                         "ORDER BY priority, id LIMIT 1", (run_id,)).fetchone()
                if task is None:
                    break
                self.conn.execute("UPDATE frontier SET status='in_progress', attempts=attempts+1, updated_at=? "
                                  "WHERE id=?", (_now(), task["id"]))
                used += 1
                try:
                    if task["kind"] == "detail":
                        self._do_detail(run_id, task)
                    else:
                        self._do_index(run_id, task)
                    self.conn.execute("UPDATE frontier SET status='done', updated_at=? WHERE id=?", (_now(), task["id"]))
                except DisallowedError as exc:
                    self.stats["disallowed"] += 1
                    self.conn.execute("UPDATE frontier SET status='skipped', last_error=? WHERE id=?",
                                      (str(exc), task["id"]))
                except BlockedError:
                    self.conn.execute("UPDATE frontier SET status='pending' WHERE id=?", (task["id"],))
                    raise
                except NetworkError as exc:
                    net_failures += 1
                    self.stats["errors"] += 1
                    self.conn.execute("UPDATE frontier SET status='pending', last_error=? WHERE id=?",
                                      (str(exc)[:500], task["id"]))
                    if net_failures >= 3:
                        raise
                    continue
                except Exception as exc:  # egy hibás oldal ne állítsa le a futást
                    self.stats["errors"] += 1
                    log.warning("Hiba (%s): %s", task["url"], exc)
                    log.debug("részletek", exc_info=True)
                    permanent = "HTTP 404" in str(exc) or "HTTP 410" in str(exc)
                    st = "failed" if permanent or task["attempts"] + 1 >= 3 else "pending"
                    self.conn.execute("UPDATE frontier SET status=?, last_error=? WHERE id=?",
                                      (st, str(exc)[:500], task["id"]))
                net_failures = 0
                self.conn.commit()
                if used % 10 == 0:
                    self._report(run_id)
        except BlockedError as exc:
            status, message = "blocked", f"A forrás korlátozta a hozzáférést: {exc}. A futás leállt (nem kerüljük meg)."
            self.conn.execute("UPDATE frontier SET status='pending' WHERE run_id=? AND status='in_progress'", (run_id,))
            self.stats["blocked"] += 1
            log.error(message)
        except NetworkError as exc:
            status, message = "failed", (f"A forrás hálózati szinten nem érhető el ({exc}). "
                                         "Ellenőrizd az internetkapcsolatot / proxy- vagy tűzfalszabályt; "
                                         "a következő indítás innen folytatja.")
            log.error(message)
        except (_Stop, KeyboardInterrupt) as exc:
            status, message = "interrupted", f"Megszakítva ({exc or 'Ctrl+C'}); a következő futás folytatja."
            log.warning(message)
        finally:
            if old_handler is not None:
                signal.signal(signal.SIGTERM, old_handler)
            self.conn.commit()

        if status == "completed":
            self._mark_missing(run_id)
        cov = coverage(self.conn, run_id)
        self.stats["http"] = dict(self.fetcher.stats)
        self.conn.execute("UPDATE crawl_runs SET finished_at=?, status=?, stats=?, message=? WHERE id=?",
                          (_now(), status, json.dumps({**self.stats, "coverage": cov}, ensure_ascii=False),
                           message, run_id))
        self.conn.commit()
        self.progress(1.0, f"Bejárás {status}")
        return {"run_id": run_id, "status": status, "message": message, "stats": self.stats, "coverage": cov}

    def _report(self, run_id):
        row = self.conn.execute("SELECT SUM(status IN ('done','failed','skipped')) d, COUNT(*) n FROM frontier "
                                "WHERE run_id=?", (run_id,)).fetchone()
        done, total = row["d"] or 0, row["n"] or 1
        self.progress(done / total, f"{done}/{total} feladat, {self.stats['cards']} kártya, "
                                    f"{self.stats['detail_pages']} termékoldal")

    # -- index pages ----------------------------------------------------------
    def _do_index(self, run_id: int, task) -> None:
        ttl = settings.get("http.cache_ttl_search_sec", 3600)
        resp = self.fetcher.get(task["url"], ttl=ttl)
        scope = task["query"] or task["url"]
        if resp is None or resp.status != 200:
            raise RuntimeError(f"index oldal nem tölthető: HTTP {getattr(resp, 'status', '-')}")
        self.stats["index_pages"] += 1
        page = self.source.parse_index(task["url"], resp.text)
        seen = self._scope_seen.setdefault(scope, set())
        new_in_scope = [c for c in page.cards if c.source_id not in seen]
        seen.update(c.source_id for c in page.cards)

        now = _now()
        for card in page.cards:
            self._handle_card(run_id, card, now, scope)

        self.conn.execute(
            "INSERT INTO coverage(run_id, source, scope, reported_total, pages_fetched, listings_seen) "
            "VALUES(?,?,?,?,1,?) ON CONFLICT(run_id, source, scope) DO UPDATE SET "
            "pages_fetched=pages_fetched+1, listings_seen=listings_seen+excluded.listings_seen, "
            "reported_total=COALESCE(coverage.reported_total, excluded.reported_total)",
            (run_id, self.source.name, scope, page.reported_total, len(new_in_scope)))

        cov = self.conn.execute("SELECT * FROM coverage WHERE run_id=? AND source=? AND scope=?",
                                (run_id, self.source.name, scope)).fetchone()
        exhausted = (not page.cards or not new_in_scope or page.has_next is False or
                     (cov["reported_total"] is not None and cov["listings_seen"] >= cov["reported_total"]))
        if exhausted:
            self.conn.execute("UPDATE coverage SET exhausted=1 WHERE run_id=? AND source=? AND scope=?",
                              (run_id, self.source.name, scope))
        elif task["page"] < self.cfg["max_pages_per_query"]:
            t = Task(task["kind"], task["url"], task["query"], task["page"], task["priority"])
            self._enqueue(run_id, self.source.page_task(t, task["page"] + 1))

        for cat in page.categories:
            if self.source.is_relevant_category(cat):
                self._enqueue(run_id, Task("category", cat, f"category:{cat}", 1, PRI_CATEGORY))
            elif self.full_catalog:
                self._enqueue(run_id, Task("category", cat, f"category:{cat}", 1, PRI_FULL))

    def _handle_card(self, run_id: int, card: Card, now: str, scope: str) -> None:
        self.stats["cards"] += 1
        feats = text.extract(card.title, "", card.category or "")
        relevance, reason = text.relevance(card.title, feats)
        fields = {"url": card.url, "title": card.title, "price_huf": card.price_huf,
                  "category": card.category, "relevance": relevance, "reject_reason": reason,
                  **_features_to_fields(feats), "origin": "crawl",
                  "extra": {"last_scope": scope, **card.extra}}
        existing = self.conn.execute("SELECT * FROM listings WHERE source=? AND source_id=?",
                                     (self.source.name, card.source_id)).fetchone()
        if card.sale_type == "aukcio" or (existing is None and card.sale_type):
            fields["sale_type"] = card.sale_type
        if card.expired and (existing is None or existing["status"] == "active"):
            fields["status"] = "ended"
            fields["status_reason"] = "a találati lista lejártnak jelzi"
        elif existing is None or existing["status"] in ("disappeared",):
            fields["status"] = "active"
        if existing is not None and existing["relevance"] and existing["last_checked"]:
            # a részletes oldalon (leírással) hozott döntést nem írjuk felül a kártya alapján
            fields.pop("relevance"), fields.pop("reject_reason")
            for k in list(_features_to_fields(feats)):
                fields.pop(k, None)
        lid, state = db.upsert_listing(self.conn, self.source.name, card.source_id, fields, now, run_id)
        self.stats[state] += 1
        if card.image_url:
            self.conn.execute("INSERT OR IGNORE INTO images(listing_id, url, position) VALUES(?,?,0)",
                              (lid, card.image_url))
        row = self.conn.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone()
        self._asking_record(row, feats, card.image_url, now, run_id, via="search_card")
        if self._needs_detail(row, state, card):
            self._enqueue(run_id, Task("detail", self.source.detail_url(card), None, 1, PRI_DETAIL))
        else:
            self.stats["details_skipped_fresh"] += 1

    def _asking_record(self, row, feats: dict, image_url, now: str, run_id: int, via: str) -> None:
        """Aktív fix áras / alkuképes hirdetés kínálati ára tanító-rekordként (korpusz szerint).

        Aukció aktuális licitje nem kerül ide (nem végleges ár)."""
        if (row["status"] != "active" or row["relevance"] == "rejected" or not row["price_huf"]
                or row["sale_type"] not in ("fix", "alku")):
            return
        corpus = "herend_zsolnay" if feats.get("brand") else "general"
        db.upsert_price_record(self.conn, {
            "source": self.source.name, "source_ref": row["source_id"], "market": self.source.market,
            "price_type": "asking_active", "amount": row["price_huf"], "currency": "HUF",
            "price_huf": row["price_huf"], "observed_at": now, "title": row["title"],
            "description": row["description"], "brand": feats.get("brand"), "object_type": feats.get("object_type"),
            "decor": feats.get("decor"), "size_cm": feats.get("size_cm"), "pieces": feats.get("pieces"),
            "condition": feats.get("condition"), "url": row["url"], "listing_id": row["id"],
            "dedup_key": text.dedup_key(row["title"] or "", None, row["seller"]), "corpus": corpus,
            "image_url": image_url, "provenance": {"crawl_run": run_id, "via": via,
                                                   "note": "aktív hirdetés kínálati ára – nem eladási ár"}})

    def _needs_detail(self, row, state: str, card: Card) -> bool:
        if self.corpus == "general" and not row["brand"]:
            return False   # általános korpusz: kártyaszintű adat elég (kép + ár + cím)
        if row["relevance"] == "rejected":
            return False
        if row["relevance"] != "accepted" and not self.source.is_relevant_card(card):
            # márkanév nélküli tétel: képi előszűrés a kártyaképen; részletek csak ha a képi szűrő jelöli
            return bool(row["extra"] and '"visual_match": true' in row["extra"])
        if state in ("new", "changed") or not row["last_checked"]:
            return True
        last = datetime.fromisoformat(row["last_checked"])
        return datetime.now(timezone.utc) - last > timedelta(hours=self.cfg["detail_recheck_hours"])

    # -- detail pages ---------------------------------------------------------
    def _do_detail(self, run_id: int, task) -> None:
        url = task["url"]
        resp = self.fetcher.get(url, ttl=settings.get("http.cache_ttl_detail_sec", 86400))
        m = __import__("re").search(r"(\d{6,})", url.rsplit("/", 1)[-1])
        source_id = m.group(1) if m else url
        now = _now()
        if resp is not None and resp.status in (404, 410):
            db.upsert_listing(self.conn, self.source.name, source_id,
                              {"url": url, "status": "removed", "status_reason": f"HTTP {resp.status}",
                               "last_checked": now}, now, run_id, via="detail")
            self.stats["removed"] += 1
            return
        if resp is None or not resp.text:
            raise RuntimeError("termékoldal nem tölthető")
        self.stats["detail_pages"] += 1
        d = self.source.parse_detail(url, resp.text)
        if not d:
            raise RuntimeError("termékoldal nem elemezhető")
        feats = text.extract(d["title"], d.get("description") or "", d.get("category") or "")
        relevance, reason = text.relevance(d["title"], feats)
        prev = self.conn.execute("SELECT relevance, extra FROM listings WHERE source=? AND source_id=?",
                                 (self.source.name, source_id)).fetchone()
        if relevance == "visual_candidate" and prev and prev["relevance"] == "visual_candidate":
            reason = "nincs gyártónév; képi jelölt"
        images = d.pop("images", [])
        availability = d.pop("availability", None)
        d.pop("offer_possible", None)
        payload = {k: d.get(k) for k in ("title", "description", "price_huf", "sale_type", "current_bid_huf",
                                         "bid_count", "status", "end_time")}
        detail_hash = hashlib.sha1(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        fields = {**d, **_features_to_fields(feats), "relevance": relevance, "reject_reason": reason,
                  "last_checked": now, "detail_hash": detail_hash,
                  "extra": {"availability": availability, "canonical_en": feats["canonical_en"]}}
        lid, state = db.upsert_listing(self.conn, self.source.name, source_id, fields, now, run_id, via="detail")
        for pos, img in enumerate(images):
            self.conn.execute("INSERT OR IGNORE INTO images(listing_id, url, position) VALUES(?,?,?)",
                              (lid, img, pos + 1))
        self._asking_record(self.conn.execute("SELECT * FROM listings WHERE id=?", (lid,)).fetchone(), feats,
                            images[0] if images else None, now, run_id, via="detail")
        if d["status"] in ("sold", "ended"):
            self.stats[d["status"]] += 1
        if d["status"] == "sold" and d.get("price_huf") and relevance == "accepted":
            ptype = "auction_final_bid" if d.get("sale_type") == "aukcio" else "realized_sale"
            db.upsert_price_record(self.conn, {
                "source": self.source.name, "source_ref": source_id, "market": self.source.market,
                "price_type": ptype, "amount": d["price_huf"], "currency": "HUF", "price_huf": d["price_huf"],
                "observed_at": d.get("end_time") or now, "title": d["title"],
                "description": d.get("description"), "brand": feats["brand"],
                "object_type": feats["object_type"], "decor": feats["decor"], "size_cm": feats["size_cm"],
                "pieces": feats["pieces"], "condition": feats["condition"], "url": url, "listing_id": lid,
                "dedup_key": text.dedup_key(d["title"], None, d.get("seller")),
                "provenance": {"crawl_run": run_id, "reason": d.get("status_reason"),
                               "bid_count": d.get("bid_count")}})

    # -- missing / disappeared -----------------------------------------------
    def _mark_missing(self, run_id: int) -> None:
        """Csak teljes (minden scope kimerítve) futás után jelölünk eltűntet."""
        incomplete = self.conn.execute("SELECT COUNT(*) n FROM coverage WHERE run_id=? AND exhausted=0",
                                       (run_id,)).fetchone()["n"]
        if incomplete:
            log.info("%d keresés nem ért a lapozás végére: eltűnt-jelölés kihagyva.", incomplete)
            return
        started = self.conn.execute("SELECT started_at FROM crawl_runs WHERE id=?", (run_id,)).fetchone()[0]
        self.conn.execute("UPDATE listings SET missing_runs=missing_runs+1 WHERE source=? AND status='active' "
                          "AND relevance='accepted' AND last_seen < ?", (self.source.name, started))
        n = self.conn.execute(
            "UPDATE listings SET status='disappeared', status_reason='több teljes bejárásban nem szerepelt "
            "(nem bizonyított eladás)' WHERE source=? AND status='active' AND missing_runs>=?",
            (self.source.name, self.cfg["missing_runs_before_disappeared"])).rowcount
        self.stats["disappeared"] = n
        self.conn.commit()


def coverage(conn, run_id: int) -> dict:
    rows = conn.execute("SELECT * FROM coverage WHERE run_id=?", (run_id,)).fetchall()
    scopes = []
    for r in rows:
        ratio = (min(1.0, r["listings_seen"] / r["reported_total"]) if r["reported_total"] else None)
        scopes.append({"scope": r["scope"], "reported_total": r["reported_total"], "pages": r["pages_fetched"],
                       "seen": r["listings_seen"], "exhausted": bool(r["exhausted"]), "ratio": ratio})
    pending = conn.execute("SELECT COUNT(*) FROM frontier WHERE run_id=? AND status='pending'", (run_id,)).fetchone()[0]
    failed = conn.execute("SELECT COUNT(*) FROM frontier WHERE run_id=? AND status IN ('failed','skipped')",
                          (run_id,)).fetchone()[0]
    exhausted = sum(s["exhausted"] for s in scopes)
    reported = [s for s in scopes if s["reported_total"]]
    complete = bool(scopes) and exhausted == len(scopes) and pending == 0 and failed == 0
    return {
        "scopes": len(scopes), "scopes_exhausted": exhausted, "pending_tasks": pending, "failed_tasks": failed,
        "reported_total_sum": sum(s["reported_total"] for s in reported) if reported else None,
        "seen_sum": sum(s["seen"] for s in scopes),
        "complete": complete,
        "label": "teljes (minden keresés a lapozás végéig)" if complete else "RÉSZLEGES",
        "detail": sorted(scopes, key=lambda s: s["scope"]),
    }
