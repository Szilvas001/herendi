"""SQLite adatréteg: hirdetések, árfigyelés, képek, tanítóárak, bejárások, becslések.

Egyetlen fájl (settings: paths.db_file), WAL móddal, így a dashboard olvashat,
miközben egy háttérfolyamat ír.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from . import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    description TEXT,
    category TEXT,
    brand TEXT,
    brand_basis TEXT,            -- title / text / visual / none
    object_type TEXT,
    decor TEXT,
    size_cm REAL,
    pieces INTEGER,
    condition TEXT,              -- hibatlan / serult / javitott / ismeretlen
    damage_flags TEXT,
    mark_flags TEXT,
    suspect_flags TEXT,
    sale_type TEXT,              -- fix / alku / aukcio / ismeretlen
    price_huf INTEGER,           -- fix/alku: kért ár; aukció: aktuális licit vagy kikiáltási ár
    price_kind TEXT,
    currency TEXT DEFAULT 'HUF',
    shipping_huf INTEGER,
    current_bid_huf INTEGER,
    start_bid_huf INTEGER,
    buy_now_huf INTEGER,
    bid_count INTEGER,
    end_time TEXT,               -- ISO 8601, ha ismert
    quantity INTEGER,
    seller TEXT,
    status TEXT DEFAULT 'active',  -- active / ended / sold / disappeared / removed
    status_reason TEXT,
    relevance TEXT,              -- accepted / rejected / visual_candidate
    reject_reason TEXT,
    first_seen TEXT,
    last_seen TEXT,
    last_checked TEXT,           -- utolsó termékoldal-ellenőrzés
    detail_hash TEXT,
    missing_runs INTEGER DEFAULT 0,
    origin TEXT,                 -- crawl / import:<fájl>
    extra TEXT,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS ix_listings_status ON listings(status, relevance);
CREATE INDEX IF NOT EXISTS ix_listings_brand ON listings(brand);

CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    listing_id INTEGER NOT NULL REFERENCES listings(id),
    observed_at TEXT NOT NULL,
    price_huf INTEGER,
    current_bid_huf INTEGER,
    bid_count INTEGER,
    status TEXT,
    via TEXT,                    -- search_card / detail / import
    run_id INTEGER
);
CREATE INDEX IF NOT EXISTS ix_obs_listing ON observations(listing_id, observed_at);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY,
    listing_id INTEGER REFERENCES listings(id),
    price_record_id INTEGER,
    url TEXT,
    position INTEGER,
    sha256 TEXT,
    phash TEXT,
    path TEXT,
    width INTEGER,
    height INTEGER,
    status TEXT DEFAULT 'pending',  -- pending / ok / failed / duplicate
    dup_of INTEGER,
    UNIQUE(listing_id, url)
);
CREATE INDEX IF NOT EXISTS ix_images_sha ON images(sha256);

CREATE TABLE IF NOT EXISTS embeddings (
    kind TEXT NOT NULL,          -- image / text
    ref TEXT NOT NULL,           -- image sha256 vagy szöveg hash
    model TEXT NOT NULL,
    dim INTEGER NOT NULL,
    vector BLOB NOT NULL,
    PRIMARY KEY(kind, ref, model)
);

-- Tanító- és összehasonlító árak. Az ártípus mindig explicit:
--   realized_sale        ténylegesen realizált eladási ár (pl. elkelt, igazolt)
--   auction_hammer       aukciósházi leütési ár (díjak külön mezőben)
--   auction_final_bid    lezárult piactéri aukció záró licitje licitekkel (elkelt jelzéssel)
--   asking_active        aktív hirdetés kínálati ára (NEM bizonyított érték)
--   auction_current_bid  futó aukció aktuális licitje (NEM végleges ár)
CREATE TABLE IF NOT EXISTS price_records (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    market TEXT NOT NULL,        -- HU / US
    price_type TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT NOT NULL,
    price_huf REAL,
    buyer_premium_rate REAL,
    fees_note TEXT,
    observed_at TEXT NOT NULL,   -- ár időpontja (eladás / leütés / megfigyelés)
    title TEXT,
    description TEXT,
    brand TEXT,
    object_type TEXT,
    decor TEXT,
    size_cm REAL,
    pieces INTEGER,
    condition TEXT,
    url TEXT,
    listing_id INTEGER,
    dedup_key TEXT,
    group_key TEXT,
    provenance TEXT,
    UNIQUE(source, source_ref, price_type, market)
);
CREATE INDEX IF NOT EXISTS ix_price_type ON price_records(market, price_type);

CREATE TABLE IF NOT EXISTS crawl_runs (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    mode TEXT,
    started_at TEXT,
    finished_at TEXT,
    status TEXT,                 -- running / completed / interrupted / blocked / failed
    stats TEXT,
    message TEXT
);

CREATE TABLE IF NOT EXISTS frontier (
    id INTEGER PRIMARY KEY,
    run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,          -- search / category / detail
    url TEXT NOT NULL,
    query TEXT,
    page INTEGER,
    priority INTEGER DEFAULT 50, -- kisebb = előbb
    status TEXT DEFAULT 'pending',  -- pending / done / failed / blocked / skipped
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    updated_at TEXT,
    UNIQUE(run_id, url)
);
CREATE INDEX IF NOT EXISTS ix_frontier ON frontier(run_id, status, priority);

CREATE TABLE IF NOT EXISTS coverage (
    run_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    scope TEXT NOT NULL,         -- query:<kifejezés> / category:<url>
    reported_total INTEGER,      -- a forrás által jelzett találatszám
    pages_fetched INTEGER DEFAULT 0,
    listings_seen INTEGER DEFAULT 0,
    exhausted INTEGER DEFAULT 0, -- 1 = a lapozás elérte a valódi végét
    PRIMARY KEY(run_id, source, scope)
);

CREATE TABLE IF NOT EXISTS estimates (
    listing_id INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    PRIMARY KEY(listing_id, model_version)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    params TEXT,
    status TEXT NOT NULL,        -- queued / running / done / failed / cancelled
    progress REAL DEFAULT 0,
    message TEXT,
    created_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    pid INTEGER,
    log_path TEXT
);

-- Ajánlási napló: az ajánlások későbbi ellenőrzéséhez (pl. aukció záróára).
CREATE TABLE IF NOT EXISTS recommendation_log (
    id INTEGER PRIMARY KEY,
    listing_id INTEGER NOT NULL,
    model_version TEXT NOT NULL,
    logged_at TEXT NOT NULL,
    market TEXT NOT NULL,
    price_huf INTEGER,
    sale_type TEXT,
    value_q50_huf INTEGER,
    conservative_profit_huf INTEGER,
    max_bid_huf INTEGER,
    recommended INTEGER
);
CREATE INDEX IF NOT EXISTS ix_reclog ON recommendation_log(listing_id, market);

-- pHash sáv-index: 8 × 8 bites sáv. Két kép Hamming-távolsága <= 7 esetén
-- legalább egy sávjuk azonos (skatulya-elv), így a közel-duplikátum keresés
-- nem igényel páronkénti összehasonlítást.
CREATE TABLE IF NOT EXISTS image_bands (
    band INTEGER NOT NULL,
    value INTEGER NOT NULL,
    image_id INTEGER NOT NULL,
    PRIMARY KEY(band, value, image_id)
);

-- Tömeges gyűjtés (pl. eBay API) folytatható állapota: lekérdezés × ársáv szeletek.
CREATE TABLE IF NOT EXISTS harvest_slices (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    corpus TEXT NOT NULL,
    query TEXT NOT NULL,
    category TEXT,
    price_lo REAL NOT NULL,
    price_hi REAL NOT NULL,
    status TEXT DEFAULT 'pending',   -- pending / splitting / done / failed
    reported_total INTEGER,
    fetched INTEGER DEFAULT 0,
    next_offset INTEGER DEFAULT 0,
    updated_at TEXT,
    message TEXT,
    UNIQUE(source, query, category, price_lo, price_hi)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

_local = threading.local()


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or settings.path("db_file"))
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn) -> None:
    """Visszafelé kompatibilis sémabővítések meglévő adatbázison."""
    pr = _columns(conn, "price_records")
    if "corpus" not in pr:
        # herend_zsolnay: a termék célpopulációja; general: általános porcelán/kerámia (előtanítás)
        conn.execute("ALTER TABLE price_records ADD COLUMN corpus TEXT DEFAULT 'herend_zsolnay'")
    if "image_url" not in pr:
        conn.execute("ALTER TABLE price_records ADD COLUMN image_url TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_price_corpus ON price_records(corpus, market)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_images_pr ON images(price_record_id, url) "
                 "WHERE price_record_id IS NOT NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_images_status ON images(status)")
    conn.commit()


def get_conn() -> sqlite3.Connection:
    """Szálanként egy kapcsolat az aktuális adatbázis-útvonalhoz."""
    path = str(settings.path("db_file"))
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        conn = connect(Path(path))
        _local.conn, _local.path = conn, path
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def set_meta(conn, key: str, value) -> None:
    conn.execute("INSERT INTO meta(key, value) VALUES(?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                 (key, json.dumps(value, ensure_ascii=False)))
    conn.commit()


def get_meta(conn, key: str, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"]) if row else default


LISTING_FIELDS = [
    "url", "title", "description", "category", "brand", "brand_basis", "object_type", "decor",
    "size_cm", "pieces", "condition", "damage_flags", "mark_flags", "suspect_flags",
    "sale_type", "price_huf", "price_kind", "currency", "shipping_huf", "current_bid_huf",
    "start_bid_huf", "buy_now_huf", "bid_count", "end_time", "quantity", "seller", "status",
    "status_reason", "relevance", "reject_reason", "last_checked", "detail_hash", "origin",
]


def upsert_listing(conn, source: str, source_id: str, fields: dict, seen_at: str,
                   run_id: int | None = None, via: str = "search_card") -> tuple[int, str]:
    """Beszúr vagy frissít egy hirdetést; változás esetén árfigyelési sort ír.

    Visszatér: (listing_id, 'new' | 'changed' | 'unchanged').
    Üres (None) mező nem ír felül meglévő értéket.
    """
    row = conn.execute("SELECT * FROM listings WHERE source=? AND source_id=?",
                       (source, source_id)).fetchone()
    clean = {k: v for k, v in fields.items() if k in LISTING_FIELDS and v is not None}
    extra = fields.get("extra")
    if row is None:
        cols = ["source", "source_id", "first_seen", "last_seen", *clean.keys()]
        vals = [source, source_id, seen_at, seen_at, *clean.values()]
        if extra is not None:
            cols.append("extra")
            vals.append(json.dumps(extra, ensure_ascii=False))
        cur = conn.execute(f"INSERT INTO listings({','.join(cols)}) VALUES({','.join('?' * len(vals))})",
                           vals)
        lid = cur.lastrowid
        state = "new"
    else:
        lid = row["id"]
        tracked = ("price_huf", "current_bid_huf", "bid_count", "status", "sale_type")
        changed = any(k in clean and clean[k] != row[k] for k in tracked)
        sets = dict(clean)
        sets["last_seen"] = max(seen_at, row["last_seen"] or seen_at)
        sets["missing_runs"] = 0
        if extra is not None:
            old = json.loads(row["extra"]) if row["extra"] else {}
            old.update(extra)
            sets["extra"] = json.dumps(old, ensure_ascii=False)
        conn.execute(f"UPDATE listings SET {', '.join(f'{k}=?' for k in sets)} WHERE id=?",
                     [*sets.values(), lid])
        state = "changed" if changed else "unchanged"
    if state != "unchanged":
        conn.execute(
            "INSERT INTO observations(listing_id, observed_at, price_huf, current_bid_huf, bid_count, "
            "status, via, run_id) VALUES(?,?,?,?,?,?,?,?)",
            (lid, seen_at, clean.get("price_huf"), clean.get("current_bid_huf"),
             clean.get("bid_count"), clean.get("status", row["status"] if row else "active"), via, run_id))
    return lid, state


def upsert_price_record(conn, rec: dict) -> int | None:
    cols = ["source", "source_ref", "market", "price_type", "amount", "currency", "price_huf",
            "buyer_premium_rate", "fees_note", "observed_at", "title", "description", "brand",
            "object_type", "decor", "size_cm", "pieces", "condition", "url", "listing_id",
            "dedup_key", "group_key", "provenance", "corpus", "image_url"]
    rec = {**rec, "corpus": rec.get("corpus") or "herend_zsolnay"}
    vals = [rec.get(c) for c in cols]
    if isinstance(rec.get("provenance"), (dict, list)):
        vals[cols.index("provenance")] = json.dumps(rec["provenance"], ensure_ascii=False)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols[4:])
    cur = conn.execute(
        f"INSERT INTO price_records({','.join(cols)}) VALUES({','.join('?' * len(cols))}) "
        f"ON CONFLICT(source, source_ref, price_type, market) DO UPDATE SET {updates} RETURNING id", vals)
    row = cur.fetchone()
    return row[0] if row else None
