"""Folytatható gyűjtés több forrásból, egyenesen a PostgreSQL-be.

Menet: a forrás sitemapjéből kiszűrjük a márkás tétel-URL-eket (a slug alapján,
termékoldal letöltése nélkül), majd a termékoldalakról schema.org adatot
olvasunk. Csak az kerül be, aminek legalább három képe, leírása és ára van.

A haladást a `porcelan.harvest_frontier` tábla tartja, ezért a futás bármikor
megszakítható, és ott folytatja. Bot-ellenőrzésnél az adott forrás leáll, és nem
kerüljük meg.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from . import pg, pg_ingest, settings
from .net import BlockedError, DisallowedError, Fetcher, NetworkError
from .sources.schemaorg import SchemaOrgForras

log = logging.getLogger(__name__)

FRONTIER_DDL = f"""
CREATE TABLE IF NOT EXISTS {pg.SEMA}.harvest_frontier (
    source     text NOT NULL,
    url        text NOT NULL,
    kind       text NOT NULL,              -- sitemap | item
    status     text NOT NULL DEFAULT 'pending',
    attempts   integer NOT NULL DEFAULT 0,
    last_error text,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, url)
);
CREATE INDEX IF NOT EXISTS ix_frontier_nyitott
    ON {pg.SEMA}.harvest_frontier (source, kind, status);
"""


def _most() -> datetime:
    return datetime.now(timezone.utc)


def _felvesz(conn, source: str, url: str, kind: str) -> None:
    conn.execute(f"INSERT INTO {pg.SEMA}.harvest_frontier (source, url, kind) VALUES (%s,%s,%s) "
                 f"ON CONFLICT (source, url) DO NOTHING", (source, url, kind))


def _kovetkezo(conn, source: str, kind: str):
    return conn.execute(
        f"SELECT url FROM {pg.SEMA}.harvest_frontier WHERE source=%s AND kind=%s "
        f"AND status='pending' ORDER BY url LIMIT 1", (source, kind)).fetchone()


def _lezar(conn, source: str, url: str, status: str, hiba: str | None = None) -> None:
    conn.execute(f"UPDATE {pg.SEMA}.harvest_frontier SET status=%s, last_error=%s, "
                 f"attempts=attempts+1, updated_at=now() WHERE source=%s AND url=%s",
                 (status, (hiba or "")[:500] or None, source, url))


def gyujt(source: str, max_kerés: int | None = None, ido_keret_sec: float | None = None,
          fetcher: Fetcher | None = None, pgconn=None) -> dict:
    """Egy forrás begyűjtése. Visszaadja a futás statisztikáját."""
    forras = SchemaOrgForras(source)
    fetcher = fetcher or Fetcher()
    sajat = pgconn is None
    conn = pgconn or pg.connect()
    hatarido = time.monotonic() + ido_keret_sec if ido_keret_sec else None
    stat = {"forras": source, "sitemap": 0, "tetel_talalt": 0, "termekoldal": 0,
            "bekerult": 0, "kihagyva": 0, "hiba": 0, "okok": {}}
    allapot, uzenet = "completed", ""

    try:
        pg.sema_letrehoz(conn)
        pg.particio_biztosit(conn, source)
        conn.execute(FRONTIER_DDL)
        _felvesz(conn, source, forras.sitemap_gyoker(), "sitemap")

        kerés = 0

        def keret_ok() -> bool:
            if max_kerés is not None and kerés >= max_kerés:
                raise TimeoutError("kéréskeret elérve")
            if hatarido and time.monotonic() > hatarido:
                raise TimeoutError("időkeret elérve")
            return True

        # 1. sitemapek: tétel-URL-ek összegyűjtése
        while (sor := _kovetkezo(conn, source, "sitemap")) is not None:
            keret_ok()
            url = sor["url"]
            kerés += 1
            try:
                valasz = fetcher.get(url, ttl=settings.get("http.cache_ttl_search_sec", 3600))
                if valasz is None or valasz.status != 200:
                    raise RuntimeError(f"HTTP {getattr(valasz, 'status', '-')}")
            except DisallowedError as exc:
                _lezar(conn, source, url, "skipped", str(exc))
                continue
            except (RuntimeError, ValueError) as exc:
                stat["hiba"] += 1
                _lezar(conn, source, url, "failed", str(exc))
                continue
            alsitemapek, tetelek = forras.sitemap_alatt(url, valasz.text)
            for u in alsitemapek:
                _felvesz(conn, source, u, "sitemap")
            for u in tetelek:
                _felvesz(conn, source, u, "item")
            stat["sitemap"] += 1
            stat["tetel_talalt"] += len(tetelek)
            _lezar(conn, source, url, "done")

        # 2. termékoldalak
        while (sor := _kovetkezo(conn, source, "item")) is not None:
            keret_ok()
            url = sor["url"]
            kerés += 1
            try:
                valasz = fetcher.get(url, ttl=settings.get("http.cache_ttl_detail_sec", 86400))
            except DisallowedError as exc:
                _lezar(conn, source, url, "skipped", str(exc))
                continue
            if valasz is None or valasz.status in (404, 410):
                _lezar(conn, source, url, "gone", "a tétel már nem elérhető")
                continue
            if valasz.status != 200 or not valasz.text:
                stat["hiba"] += 1
                _lezar(conn, source, url, "failed", f"HTTP {valasz.status}")
                continue
            stat["termekoldal"] += 1
            adatpont = forras.adatpont(url, valasz.text)
            if adatpont is None:
                stat["kihagyva"] += 1
                stat["okok"]["nincs schema.org Product"] = stat["okok"].get("nincs schema.org Product", 0) + 1
                _lezar(conn, source, url, "skipped", "nincs schema.org Product")
                continue
            adatpont["observed_at"] = _most()
            ok = pg.ervenyes(adatpont)
            if ok is not None:
                stat["kihagyva"] += 1
                stat["okok"][ok] = stat["okok"].get(ok, 0) + 1
                _lezar(conn, source, url, "skipped", ok)
                continue
            pg.beir(conn, adatpont)
            stat["bekerult"] += 1
            _lezar(conn, source, url, "done")

    except BlockedError as exc:
        allapot = "blocked"
        uzenet = f"A forrás korlátozta a hozzáférést: {exc}. Leálltunk, nem kerüljük meg."
        log.error(uzenet)
    except NetworkError as exc:
        allapot, uzenet = "failed", f"A forrás hálózati szinten nem érhető el: {exc}"
        log.error(uzenet)
    except (TimeoutError, KeyboardInterrupt) as exc:
        allapot = "interrupted"
        uzenet = f"Megszakítva ({exc or 'Ctrl+C'}); a következő futás folytatja."
        log.warning(uzenet)
    finally:
        if sajat:
            conn.close()

    stat["status"] = allapot
    stat["message"] = uzenet
    return stat


def osszes_forras() -> list[str]:
    cfg = settings.get("harvest") or {}
    return [nev for nev, c in cfg.items() if isinstance(c, dict) and c.get("enabled")]
