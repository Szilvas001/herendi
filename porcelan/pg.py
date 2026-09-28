"""PostgreSQL-tároló a több forrásból gyűjtött kép-ár adatpontoknak.

Egy adatpont akkor kerül be, ha **legalább három képe**, **leírása** és **ára**
van. Ezt az adatbázis maga is kikényszeríti (CHECK), nem csak a betöltő kód.

A források fizikailag el vannak választva: a `datapoints` tábla LIST-partícionált
a `source` oszlop szerint, minden forrás a saját partíciójába ír. Így
forrásonként külön táblafájl, külön statisztika és külön karbantartás, de egy
lekérdezéssel az egész korpusz látszik.

Kapcsolódás: a PG_DSN környezeti változó, vagy a settings [postgres] szakasza.
"""
from __future__ import annotations

import json
import logging
import os
import re

import psycopg
from psycopg.rows import dict_row

from . import settings

log = logging.getLogger(__name__)

SEMA = "porcelan"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS {SEMA};

CREATE TABLE IF NOT EXISTS {SEMA}.datapoints (
    id            bigint GENERATED ALWAYS AS IDENTITY,
    source        text        NOT NULL,
    source_id     text        NOT NULL,
    url           text        NOT NULL,
    market        text        NOT NULL DEFAULT 'HU',

    title         text        NOT NULL,
    description   text        NOT NULL,
    category      text,

    price_huf     bigint      NOT NULL,
    price_type    text        NOT NULL,
    price_amount  numeric,
    currency      text        NOT NULL DEFAULT 'HUF',
    sale_type     text,
    end_time      timestamptz,

    brand         text,
    object_type   text,
    decor         text,
    size_cm       real,
    pieces        integer,
    condition     text,

    relevance     text,
    corpus        text,
    image_count   integer     NOT NULL,
    observed_at   timestamptz NOT NULL,
    ingested_at   timestamptz NOT NULL DEFAULT now(),
    raw           jsonb,

    PRIMARY KEY (source, source_id),

    CONSTRAINT legalabb_harom_kep CHECK (image_count >= 3),
    CONSTRAINT van_leiras         CHECK (length(btrim(description)) >= 20),
    CONSTRAINT van_ar             CHECK (price_huf > 0)
) PARTITION BY LIST (source);

CREATE TABLE IF NOT EXISTS {SEMA}.datapoint_images (
    source      text    NOT NULL,
    source_id   text    NOT NULL,
    position    integer NOT NULL,
    url         text    NOT NULL,
    sha256      text,
    width       integer,
    height      integer,
    local_path  text,
    PRIMARY KEY (source, source_id, position),
    FOREIGN KEY (source, source_id)
        REFERENCES {SEMA}.datapoints (source, source_id) ON DELETE CASCADE
) PARTITION BY LIST (source);
"""

INDEXEK = f"""
CREATE INDEX IF NOT EXISTS ix_dp_brand      ON {SEMA}.datapoints (brand);
CREATE INDEX IF NOT EXISTS ix_dp_relevance  ON {SEMA}.datapoints (relevance);
CREATE INDEX IF NOT EXISTS ix_dp_corpus     ON {SEMA}.datapoints (corpus);
CREATE INDEX IF NOT EXISTS ix_dp_market     ON {SEMA}.datapoints (market);
CREATE INDEX IF NOT EXISTS ix_dp_price_type ON {SEMA}.datapoints (price_type);
CREATE INDEX IF NOT EXISTS ix_dp_observed   ON {SEMA}.datapoints (observed_at);
"""


def dsn() -> str:
    if os.environ.get("PG_DSN"):
        return os.environ["PG_DSN"]
    cfg = settings.get("postgres") or {}
    return (f"host={cfg.get('host', '127.0.0.1')} port={cfg.get('port', 5433)} "
            f"dbname={cfg.get('dbname', 'porcelan')} user={cfg.get('user', 'porcelan')} "
            f"password={cfg.get('password', 'herendi_local')}")


def connect(autocommit: bool = True) -> psycopg.Connection:
    return psycopg.connect(dsn(), row_factory=dict_row, autocommit=autocommit)


def adatbazis_letrehoz() -> None:
    """A `porcelan` adatbázis létrehozása, ha még nincs (a postgres DB-n át)."""
    cfg = settings.get("postgres") or {}
    nev = cfg.get("dbname", "porcelan")
    admin = dsn().replace(f"dbname={nev}", "dbname=postgres")
    with psycopg.connect(admin, autocommit=True) as conn:
        van = conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (nev,)).fetchone()
        if not van:
            conn.execute(f'CREATE DATABASE "{nev}"')
            log.info("Adatbázis létrehozva: %s", nev)


def _particio_nev(source: str) -> str:
    tiszta = re.sub(r"[^a-z0-9_]", "_", source.lower())
    if not tiszta or tiszta[0].isdigit():
        raise ValueError(f"nem használható forrásnév: {source!r}")
    return tiszta


def particio_biztosit(conn, source: str) -> None:
    """Forrásonkénti partíció létrehozása mindkét táblához.

    A partícióhatár nem lehet lekérdezés-paraméter, ezért a forrásnevet
    literálként írjuk be – a `_particio_nev` előtte szűk karakterkészletre
    korlátozza, a literált pedig a psycopg idézi.
    """
    from psycopg import sql

    p = _particio_nev(source)
    for tabla in ("datapoints", "datapoint_images"):
        conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {particio} "
                             "PARTITION OF {szulo} FOR VALUES IN ({ertek})").format(
            particio=sql.Identifier(SEMA, f"{tabla}_{p}"),
            szulo=sql.Identifier(SEMA, tabla),
            ertek=sql.Literal(source)))


def sema_letrehoz(conn=None) -> None:
    sajat = conn is None
    conn = conn or connect()
    try:
        conn.execute(DDL)
        conn.execute(INDEXEK)
    finally:
        if sajat:
            conn.close()


MEZOK = ("source", "source_id", "url", "market", "title", "description", "category",
         "price_huf", "price_type", "price_amount", "currency", "sale_type", "end_time",
         "brand", "object_type", "decor", "size_cm", "pieces", "condition",
         "relevance", "corpus", "image_count", "observed_at", "raw")


def ervenyes(adatpont: dict) -> str | None:
    """A felvételi feltétel kódban is: legalább 3 kép, leírás, ár. None = rendben."""
    kepek = adatpont.get("images") or []
    if len(kepek) < 3:
        return f"csak {len(kepek)} kép"
    if len((adatpont.get("description") or "").strip()) < 20:
        return "nincs érdemi leírás"
    if not adatpont.get("price_huf"):
        return "nincs ár"
    if not adatpont.get("title"):
        return "nincs cím"
    return None


def beir(conn, adatpont: dict) -> bool:
    """Egy adatpont beírása a forrás partíciójába. True, ha bekerült."""
    if ervenyes(adatpont) is not None:
        return False
    kepek = adatpont["images"][:24]
    sor = {k: adatpont.get(k) for k in MEZOK}
    sor["image_count"] = len(kepek)
    sor["raw"] = json.dumps(adatpont.get("raw") or {}, ensure_ascii=False)

    oszlopok = ", ".join(MEZOK)
    helyek = ", ".join(f"%({k})s" for k in MEZOK)
    frissit = ", ".join(f"{k}=EXCLUDED.{k}" for k in MEZOK
                        if k not in ("source", "source_id"))
    conn.execute(f"INSERT INTO {SEMA}.datapoints ({oszlopok}) VALUES ({helyek}) "
                 f"ON CONFLICT (source, source_id) DO UPDATE SET {frissit}", sor)

    conn.execute(f"DELETE FROM {SEMA}.datapoint_images WHERE source=%s AND source_id=%s",
                 (adatpont["source"], adatpont["source_id"]))
    for i, kep in enumerate(kepek):
        if isinstance(kep, str):
            kep = {"url": kep}
        conn.execute(
            f"INSERT INTO {SEMA}.datapoint_images (source, source_id, position, url, sha256, "
            f"width, height, local_path) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
            f"ON CONFLICT (source, source_id, position) DO UPDATE SET url=EXCLUDED.url",
            (adatpont["source"], adatpont["source_id"], i, kep["url"], kep.get("sha256"),
             kep.get("width"), kep.get("height"), kep.get("local_path")))
    return True


def statisztika(conn) -> list[dict]:
    return conn.execute(
        f"SELECT source, count(*) AS adatpont, sum(image_count) AS kep, "
        f"count(*) FILTER (WHERE price_type IN ('auction_final_bid','realized_sale')) AS realizalt, "
        f"count(*) FILTER (WHERE corpus='herend_zsolnay') AS markas, "
        f"max(market) AS piac, "
        f"min(observed_at) AS legkorabbi, max(observed_at) AS legfrissebb "
        f"FROM {SEMA}.datapoints GROUP BY source ORDER BY adatpont DESC").fetchall()
