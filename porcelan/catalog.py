"""Termékkatalógus és pontos (cikkszám-szintű) azonosítás szövegből és képből.

Források:
- Katalógus-CSV (config/catalog.example.csv fejléccel): gyártói webshop-export,
  saját gyűjtés. Oszlopok: brand, form_no, pattern_code, name, object_type, size_cm,
  retail_price, currency, retail_market, url, image_url.
- Gyártói termékoldal (pl. herend.com/termek/…): schema.org Product JSON-LD
  alapján; a cikkszámot a névből / SKU mezőből olvassa. Élesben ellenőrizendő.

Képi azonosítás: a katalógusképek ÉS a szövegből biztosan azonosított hirdetések
képei alkotják a mintatárat; egy új kép a legközelebbi minták cikkszámára szavaz
(CLIP-beágyazás). A pontosságot a mintatáron, kihagyásos (leave-one-out)
módszerrel mérjük – a küszöb e mérés alapján dől el, nem feltételezés.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path

import numpy as np

from . import db, text, vision
from .identify import Identity, identify_text

log = logging.getLogger(__name__)
TEXT_ID_MIN_CONF = 0.75          # ennyi felett a szöveges azonosítás mintának elfogadható


def sku_key(brand, form_no, pattern) -> str:
    return f"{brand}|{str(form_no).lstrip('0')}|{pattern or '-'}"


def upsert_catalog_item(conn, it: dict) -> int:
    form = str(it["form_no"]).lstrip("0")
    key = sku_key(it["brand"], form, it.get("pattern_code"))
    cols = ["brand", "form_no", "pattern_code", "sku_key", "name", "object_type", "size_cm", "retail_price",
            "currency", "retail_market", "source", "url", "image_url", "observed_at"]
    vals = [it.get("brand"), form, it.get("pattern_code") or None, key, it.get("name"), it.get("object_type"),
            it.get("size_cm"), it.get("retail_price"), it.get("currency"), it.get("retail_market"),
            it.get("source"), it.get("url"), it.get("image_url"), it.get("observed_at") or db.now_iso()]
    row = conn.execute(f"INSERT INTO catalog_items({','.join(cols)}) VALUES({','.join('?' * len(cols))}) "
                       f"ON CONFLICT(sku_key) DO UPDATE SET {', '.join(f'{c}=COALESCE(excluded.{c}, {c})' for c in cols[4:])} "
                       f"RETURNING id", vals).fetchone()
    cid = row[0]
    if it.get("image_url"):
        conn.execute("INSERT OR IGNORE INTO images(catalog_id, url, position) VALUES(?,?,0)", (cid, it["image_url"]))
    return cid


def import_catalog_csv(path: Path, conn=None) -> dict:
    conn = conn or db.get_conn()
    n, skipped = 0, 0
    with Path(path).open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if not r.get("brand") or not (r.get("form_no") or "").strip().isdigit():
                skipped += 1
                continue
            upsert_catalog_item(conn, {
                **r, "size_cm": float(r["size_cm"]) if r.get("size_cm") else None,
                "retail_price": float(r["retail_price"]) if r.get("retail_price") else None,
                "source": r.get("source") or f"csv:{Path(path).name}"})
            n += 1
    conn.commit()
    return {"items": n, "skipped": skipped}


def parse_manufacturer_page(url: str, html: str, brand: str = "Herendi") -> dict | None:
    """Gyártói termékoldal → katalógus-tétel (schema.org Product JSON-LD)."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "{}")
        except (ValueError, TypeError):
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict) or node.get("@type") != "Product":
                continue
            name = node.get("name") or ""
            ident = identify_text(f"{name} {node.get('sku') or ''} {node.get('mpn') or ''}",
                                  node.get("description") or "", brand)
            if not ident.form_no:
                return None
            offer = node.get("offers") or {}
            offer = offer[0] if isinstance(offer, list) and offer else offer
            img = node.get("image")
            img = img[0] if isinstance(img, list) and img else img
            f = text.extract(name, node.get("description") or "")
            return {"brand": brand, "form_no": ident.form_no, "pattern_code": ident.pattern, "name": name,
                    "object_type": f["object_type"], "size_cm": f["size_cm"],
                    "retail_price": float(offer["price"]) if offer.get("price") else None,
                    "currency": offer.get("priceCurrency"), "retail_market": "HU" if ".hu" in url or "herend.com" in url else None,
                    "source": "manufacturer", "url": url, "image_url": img if isinstance(img, str) else None}
    return None


# ---------------------------------------------------------------------------
# Szöveges azonosítás tárolása
# ---------------------------------------------------------------------------
def identify_all_text(conn=None) -> dict:
    """Minden hirdetés és ár-rekord szöveges azonosítása (cikkszám-kulcs mezők)."""
    conn = conn or db.get_conn()
    stats = {"listings": 0, "listings_sku": 0, "records": 0, "records_sku": 0}
    for table, key in (("listings", "listings"), ("price_records", "records")):
        rows = conn.execute(f"SELECT id, title, description, brand FROM {table} WHERE brand IS NOT NULL").fetchall()
        upd = []
        for r in rows:
            i = identify_text(r["title"] or "", r["description"] or "", r["brand"])
            upd.append((i.sku_key, i.form_no, i.pattern, i.confidence, json.dumps(["szöveg"] + i.basis,
                                                                                   ensure_ascii=False), r["id"]))
            stats[key] += 1
            stats[f"{key}_sku"] += bool(i.form_no and i.pattern)
        conn.executemany(f"UPDATE {table} SET sku_key=?, form_no=?, pattern_code=?, id_confidence=?, id_basis=? "
                         f"WHERE id=?", upd)
    conn.commit()
    return stats


# ---------------------------------------------------------------------------
# Képi azonosítás
# ---------------------------------------------------------------------------
def _exemplars(conn, tag: str):
    """(vektorok, cikkszám-kulcsok, forrásazonosítók) a mintatárhoz."""
    vecs, keys, refs = [], [], []
    rows = conn.execute("SELECT i.catalog_id, c.sku_key, e.vector FROM images i JOIN catalog_items c ON c.id=i.catalog_id "
                        "JOIN embeddings e ON e.kind='image' AND e.ref=i.sha256 AND e.model=? "
                        "WHERE i.catalog_id IS NOT NULL AND i.status IN ('ok','duplicate')", (tag,)).fetchall()
    for r in rows:
        vecs.append(np.frombuffer(r["vector"], np.float32))
        keys.append(r["sku_key"])
        refs.append(f"catalog:{r['catalog_id']}")
    rows = conn.execute("SELECT l.id, l.sku_key, e.vector FROM listings l JOIN images i ON i.listing_id=l.id "
                        "JOIN images o ON o.id=COALESCE(i.dup_of, i.id) "
                        "JOIN embeddings e ON e.kind='image' AND e.ref=o.sha256 AND e.model=? "
                        "WHERE l.sku_key IS NOT NULL AND l.pattern_code IS NOT NULL AND l.id_confidence>=? "
                        "AND i.status IN ('ok','duplicate')", (tag, TEXT_ID_MIN_CONF)).fetchall()
    for r in rows:
        vecs.append(np.frombuffer(r["vector"], np.float32))
        keys.append(r["sku_key"])
        refs.append(f"listing:{r['id']}")
    return (np.stack(vecs) if vecs else np.zeros((0, vision.DIM), np.float32)), keys, refs


def _vote(sims: np.ndarray, keys: list[str], k: int = 5) -> tuple[str | None, float, float]:
    """(legvalószínűbb cikkszám, pontszám, különbség a második legjobbhoz)."""
    if len(sims) == 0:
        return None, 0.0, 0.0
    idx = np.argsort(-sims)[:k]
    score: dict = {}
    for j in idx:
        score[keys[j]] = score.get(keys[j], 0.0) + float(np.exp((sims[j] - 1) * 20))
    ranked = sorted(score.items(), key=lambda x: -x[1])
    tot = sum(v for _, v in ranked)
    best, s1 = ranked[0]
    s2 = ranked[1][1] if len(ranked) > 1 else 0.0
    return best, s1 / tot, (s1 - s2) / tot


def evaluate_image_identification(conn=None) -> dict:
    """Kihagyásos pontosság a mintatáron: a képből jósolt cikkszám = a szöveg/katalógus szerinti?

    A pontosságot a szavazati pontszám szerinti sávokban is megadja – ebből jön a
    küszöb, amely felett a képi azonosítás elfogadható."""
    conn = conn or db.get_conn()
    tag = vision.EMB_TAG
    X, keys, refs = _exemplars(conn, tag)
    if len(keys) < 20:
        return {"n": len(keys), "note": "kevés azonosított, képes minta – a képi azonosítás még nem mérhető"}
    sims = X @ X.T
    rows = []
    for i in range(len(keys)):
        s = sims[i].copy()
        same_src = [j for j, r in enumerate(refs) if r == refs[i]]
        s[same_src] = -np.inf
        pred, score, margin = _vote(np.where(np.isfinite(s), s, -1.0), keys)
        rows.append((score, pred == keys[i]))
    rows.sort()
    out = {"n": len(rows), "top1_accuracy": float(np.mean([ok for _, ok in rows])), "bands": []}
    for lo in (0.0, 0.5, 0.7, 0.85, 0.95):
        sel = [ok for sc, ok in rows if sc >= lo]
        if sel:
            out["bands"].append({"min_score": lo, "coverage": len(sel) / len(rows), "accuracy": float(np.mean(sel))})
    ok_bands = [b for b in out["bands"] if b["accuracy"] >= 0.95 and len(rows) * b["coverage"] >= 20]
    out["recommended_min_score"] = ok_bands[0]["min_score"] if ok_bands else None
    db.set_meta(conn, "image_identification_eval", out)
    return out


def identify_images(conn=None, min_score: float | None = None) -> dict:
    """Szöveg alapján nem (teljesen) azonosított hirdetések képi azonosítása.

    Csak a mért, ≥95%-os pontosságú pontszámsáv felett fogad el (evaluate_image_identification)."""
    conn = conn or db.get_conn()
    if min_score is None:
        ev = db.get_meta(conn, "image_identification_eval") or evaluate_image_identification(conn)
        min_score = ev.get("recommended_min_score")
    if min_score is None:
        return {"identified": 0, "note": "a képi azonosítás pontossága még nem igazolt (kevés minta)"}
    tag = vision.EMB_TAG
    X, keys, _ = _exemplars(conn, tag)
    if not len(keys):
        return {"identified": 0}
    cands = [r["id"] for r in conn.execute(
        "SELECT id FROM listings WHERE relevance='accepted' AND (pattern_code IS NULL OR form_no IS NULL "
        "OR COALESCE(id_confidence,0) < ?)", (TEXT_ID_MIN_CONF,))]
    vecs = vision.listing_image_vectors(conn, cands, tag)
    n = 0
    for lid, v in vecs.items():
        pred, score, margin = _vote(X @ v, keys)
        if pred and score >= min_score:
            brand, form, pat = pred.split("|")
            conn.execute("UPDATE listings SET sku_key=?, form_no=?, pattern_code=?, id_confidence=?, id_basis=? "
                         "WHERE id=?", (pred, form, None if pat == "-" else pat, round(score, 3),
                                        json.dumps(["kép", f"pontszám {score:.2f}"], ensure_ascii=False), lid))
            conn.execute("UPDATE price_records SET sku_key=?, form_no=?, pattern_code=?, id_confidence=?, id_basis=? "
                         "WHERE listing_id=? AND (sku_key IS NULL OR COALESCE(id_confidence,0) < ?)",
                         (pred, form, None if pat == "-" else pat, round(score, 3), '["kép"]', lid, score))
            n += 1
    conn.commit()
    return {"identified": n, "min_score": min_score, "candidates": len(cands), "with_images": len(vecs)}


def identity_of(row) -> Identity:
    """Tárolt azonosítás egy hirdetés/ár-rekord sorából."""
    if not row["sku_key"]:
        return Identity(brand=row["brand"])
    brand, form, pat = row["sku_key"].split("|")
    basis = json.loads(row["id_basis"]) if row["id_basis"] else []
    return Identity(brand=brand, form_no=form, part="0", pattern=None if pat == "-" else pat,
                    confidence=row["id_confidence"] or 0.0, basis=basis)


def sku_from_title(title: str) -> str | None:
    """Kényelmi függvény: a cím szöveges cikkszám-kulcsa (csak formaszám+minta esetén)."""
    i = identify_text(title)
    return i.sku_key if i.form_no and i.pattern else None



# ---------------------------------------------------------------------------
# herend.com hivatalos katalógus (robots.txt: minden engedélyezett; sitemap.xml)
# ---------------------------------------------------------------------------
HEREND_SITEMAP = "https://herend.com/sitemap.xml"
_HEREND_SKU = re.compile(r"^(\d{5})(\d)(\d{2})([A-Z0-9][A-Z0-9\-]*)?$")


def parse_herend_sku(code: str) -> dict | None:
    """'03464000SPEB' → formaszám 3464, alkatrész 0, fogantyú 00, minta SPEB."""
    m = _HEREND_SKU.match((code or "").strip().upper())
    if not m:
        return None
    return {"form_no": m.group(1).lstrip("0") or "0", "part": m.group(2), "knob": m.group(3),
            "pattern_code": m.group(4) or None}


def parse_herend_product(url: str, html: str) -> dict | None:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html or "", "html.parser")
    props = {}
    for it in soup.select(".description__table__item"):
        parts = [x.get_text(" ", strip=True) for x in it.find_all(["span", "div"])]
        if len(parts) >= 2:
            props[parts[0]] = parts[1]
    code = props.get("Cikkszám")
    if not code:
        return None
    sku = parse_herend_sku(code)
    if not sku:
        return None
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    name = title.split(" - ")[0].strip() or code
    dims = []
    for k in ("Magasság", "Átmérő", "Szélesség", "Hossz"):
        m = re.match(r"([\d.,]+)\s*mm", props.get(k, ""))
        if m:
            dims.append(float(m.group(1).replace(",", ".")) / 10)
    img = re.search(r"https://herend\.com/image\?src=(uploads%2Fimages%2Fproducts%2F[^&\"')]+)", html or "")
    image_url = f"https://herend.com/image?src={img.group(1)}&w=512&h=512" if img else None
    f = text.extract(name)
    return {"brand": "Herendi", "form_no": sku["form_no"], "pattern_code": sku["pattern_code"],
            "name": f"{name} ({code})", "object_type": f["object_type"], "size_cm": max(dims) if dims else None,
            "retail_price": None, "currency": None, "retail_market": None, "source": "herend.com",
            "url": url, "image_url": image_url,
            "extra": {"code": code, "part": sku["part"], "knob": sku["knob"], "props": props}}


def crawl_herend_catalog(conn=None, fetcher=None, limit: int | None = None, progress=None) -> dict:
    """A hivatalos herend.com katalógus bejárása a sitemapből (folytatható: a már meglévő
    cikkszámokat nem tölti le újra). Ár a statikus oldalon nincs; cikkszám, név, méret, kép van."""
    from .net import BlockedError, Fetcher, NetworkError
    conn = conn or db.get_conn()
    fetcher = fetcher or Fetcher()
    sm = fetcher.get(HEREND_SITEMAP, ttl=86400)
    if sm is None or sm.status != 200:
        raise RuntimeError("herend.com sitemap nem tölthető")
    urls = [u for u in re.findall(r"<loc>([^<]+)</loc>", sm.text) if "/termek/" in u and "/en/" not in u]
    done = {r[0] for r in conn.execute("SELECT url FROM catalog_items WHERE source='herend.com'")}
    todo = [u for u in urls if u not in done][: limit or None]
    stats = {"sitemap_products": len(urls), "already": len(done), "fetched": 0, "stored": 0, "failed": 0}
    for i, u in enumerate(todo, 1):
        try:
            resp = fetcher.get(u, ttl=30 * 86400)
        except (BlockedError, NetworkError) as exc:
            stats["stopped"] = str(exc)
            break
        stats["fetched"] += 1
        item = parse_herend_product(u, resp.text if resp else "")
        if item:
            upsert_catalog_item(conn, item)
            stats["stored"] += 1
        else:
            stats["failed"] += 1
        if i % 25 == 0:
            conn.commit()
            if progress:
                progress(i / len(todo), f"herend.com: {i}/{len(todo)} termékoldal")
    conn.commit()
    return stats
