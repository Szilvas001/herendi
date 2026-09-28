"""Képletöltés, tartalom-hash, perceptuális hash és duplikátumszűrés.

- sha256: bájtazonos képek (ugyanaz a fotó több hirdetésben),
- pHash (64 bites DCT): közel azonos képek (átméretezés, újratömörítés);
  Hamming-távolság <= PHASH_DUP_BITS esetén duplikátum.
A duplikátum-információ a tanítóhalmaz csoportos felosztásához is kell:
közel azonos képű hirdetés nem kerülhet külön halmazba.
"""
from __future__ import annotations

import hashlib
import io
import logging
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from . import db, settings
from .net import BlockedError, DisallowedError, Fetcher, NetworkError

log = logging.getLogger(__name__)
PHASH_DUP_BITS = 6
MAX_SIDE = 640


def _dct_matrix(n: int) -> np.ndarray:
    k = np.arange(n)
    m = np.cos(np.pi * (2 * k[None, :] + 1) * k[:, None] / (2 * n))
    m[0] *= 1 / np.sqrt(2)
    return m * np.sqrt(2 / n)


_DCT32 = _dct_matrix(32)


def phash(img: Image.Image) -> str:
    """64 bites pHash hexben (32x32 szürke → DCT → bal felső 8x8 a medián felett)."""
    g = np.asarray(img.convert("L").resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    d = _DCT32 @ g @ _DCT32.T
    low = d[:8, :8].flatten()
    bits = low[1:] > np.median(low[1:])
    bits = np.concatenate([[False], bits])
    return f"{int(''.join('1' if b else '0' for b in bits), 2):016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def store_image_bytes(data: bytes) -> dict:
    """Normalizált JPEG mentése tartalom-cím szerint; hash-ek számítása."""
    sha = hashlib.sha256(data).hexdigest()
    img = Image.open(io.BytesIO(data))
    img.load()
    img = img.convert("RGB")
    ph = phash(img)
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    rel = Path(sha[:2]) / f"{sha}.jpg"
    dest = settings.path("image_dir") / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        img.save(dest, "JPEG", quality=88)
    return {"sha256": sha, "phash": ph, "path": str(rel), "width": w, "height": h}


def bands(ph: str) -> list[tuple[int, int]]:
    """8 db 8 bites sáv. Hamming <= 7 esetén legalább egy sáv egyezik."""
    v = int(ph, 16)
    return [(b, (v >> (8 * b)) & 0xFF) for b in range(8)]


def index_bands(conn, image_id: int, ph: str) -> None:
    conn.executemany("INSERT OR IGNORE INTO image_bands(band, value, image_id) VALUES(?,?,?)",
                     [(b, val, image_id) for b, val in bands(ph)])


def find_duplicate(conn, image_id: int, sha: str, ph: str) -> int | None:
    row = conn.execute("SELECT id FROM images WHERE sha256=? AND id<>? AND status='ok' ORDER BY id LIMIT 1",
                       (sha, image_id)).fetchone()
    if row:
        return row["id"]
    # jelöltek a sáv-indexből (nem páronkénti keresés), majd pontos Hamming-ellenőrzés
    cands = set()
    for b, val in bands(ph):
        for r in conn.execute("SELECT image_id FROM image_bands WHERE band=? AND value=? AND image_id<>? LIMIT 200",
                              (b, val, image_id)):
            cands.add(r[0])
    best = None
    for cid in sorted(cands):
        r = conn.execute("SELECT phash, status FROM images WHERE id=?", (cid,)).fetchone()
        if r and r["status"] == "ok" and r["phash"] and hamming(r["phash"], ph) <= PHASH_DUP_BITS:
            best = cid
            break
    return best


def download_pending(conn=None, fetcher: Fetcher | None = None, limit: int | None = None,
                     progress=None, corpus: str | None = None) -> dict:
    """Függő képek letöltése hirdetésekhez és ár-rekordokhoz (pl. eBay-korpusz)."""
    conn = conn or db.get_conn()
    fetcher = fetcher or Fetcher(min_delay=settings.get("http.min_delay_sec") / 2)
    q = ("SELECT i.id, i.url FROM images i LEFT JOIN listings l ON l.id=i.listing_id "
         "LEFT JOIN price_records p ON p.id=i.price_record_id "
         "WHERE i.status='pending' AND (l.relevance IN ('accepted','visual_candidate') OR p.id IS NOT NULL)")
    args: list = []
    if corpus:
        q += " AND p.corpus=?"
        args.append(corpus)
    q += " ORDER BY i.id"
    if limit:
        q += f" LIMIT {int(limit)}"
    rows = conn.execute(q, args).fetchall()
    stats = {"ok": 0, "duplicate": 0, "failed": 0, "blocked": 0, "network": 0}
    for n, r in enumerate(rows, 1):
        try:
            resp = fetcher.get(r["url"], ttl=30 * 86400, binary=True)
            if resp is None or resp.status != 200 or not resp.content:
                raise RuntimeError(f"HTTP {getattr(resp, 'status', '-')}")
            info = store_image_bytes(resp.content)
        except BlockedError as exc:
            stats["blocked"] += 1
            log.error("Képforrás korlátozott, leállás: %s", exc)
            break
        except NetworkError as exc:
            stats["network"] += 1
            if stats["network"] >= 3:
                log.error("Képforrás nem érhető el, leállás: %s", exc)
                break
            continue
        except (DisallowedError, RuntimeError, UnidentifiedImageError, OSError) as exc:
            conn.execute("UPDATE images SET status='failed' WHERE id=?", (r["id"],))
            stats["failed"] += 1
            log.debug("kép hiba %s: %s", r["url"], exc)
            continue
        dup = find_duplicate(conn, r["id"], info["sha256"], info["phash"])
        conn.execute("UPDATE images SET sha256=?, phash=?, path=?, width=?, height=?, status=?, dup_of=? WHERE id=?",
                     (info["sha256"], info["phash"], info["path"], info["width"], info["height"],
                      "duplicate" if dup else "ok", dup, r["id"]))
        if not dup:
            index_bands(conn, r["id"], info["phash"])
        stats["duplicate" if dup else "ok"] += 1
        if n % 50 == 0:
            conn.commit()
            if progress:
                progress(n / len(rows), f"{n}/{len(rows)} kép")
    conn.commit()
    return stats


def listing_images(conn, listing_id: int) -> list[dict]:
    """A hirdetés képei (duplikátumok az eredeti fájlra mutatnak)."""
    out = []
    for r in conn.execute("SELECT * FROM images WHERE listing_id=? ORDER BY position, id", (listing_id,)):
        path = r["path"]
        if r["status"] == "duplicate" and r["dup_of"]:
            orig = conn.execute("SELECT path FROM images WHERE id=?", (r["dup_of"],)).fetchone()
            path = orig["path"] if orig else path
        out.append({"url": r["url"], "local": path, "status": r["status"], "sha256": r["sha256"]})
    return out
