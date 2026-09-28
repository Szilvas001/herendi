"""Előtanított multimodális képi modell (OpenCLIP ViT-B/32, LAION-400M).

- kép- és szövegbeágyazás közös 512 dimenziós térben (cache: `embeddings` tábla),
- zero-shot képi előszűrés a gyártónév nélküli porcelánhirdetésekhez,
- a súlyfájlt a GitHub release-ből tölti le, SHA-256 ellenőrzéssel.

Nem tanítunk nulláról: a CLIP-enkóder fagyasztott, rá kis becslőfej épül
(`porcelan/model.py`).
"""
from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path

import numpy as np

from . import db, settings

log = logging.getLogger(__name__)
MODEL_NAME = "ViT-B-32-quickgelu"
EMB_TAG = "openclip-vitb32-laion400m"
DIM = 512

_lock = threading.Lock()
_model = None


class VisionUnavailable(RuntimeError):
    pass


def weights_path() -> Path:
    return settings.path("clip_weights")


def ensure_weights(download: bool = True) -> Path:
    p = weights_path()
    expected = settings.get("paths.clip_weights_sha256")
    if p.exists():
        return p
    if not download:
        raise VisionUnavailable(f"Hiányzó CLIP-súlyfájl: {p}")
    import requests
    p.parent.mkdir(parents=True, exist_ok=True)
    url = settings.get("paths.clip_weights_url")
    log.info("CLIP-súlyok letöltése: %s", url)
    tmp = p.with_suffix(".part")
    h = hashlib.sha256()
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in r.iter_content(1 << 20):
                fh.write(chunk)
                h.update(chunk)
    if expected and h.hexdigest() != expected:
        tmp.unlink(missing_ok=True)
        raise VisionUnavailable("A CLIP-súlyfájl ellenőrzőösszege nem egyezik.")
    tmp.rename(p)
    return p


def load(download: bool = False):
    """(model, preprocess, tokenizer) – egyszer töltődik be folyamatonként."""
    global _model
    with _lock:
        if _model is None:
            try:
                import open_clip
                import torch
            except ImportError as exc:
                raise VisionUnavailable("open_clip_torch / torch nincs telepítve") from exc
            torch.set_num_threads(max(1, torch.get_num_threads()))
            path = ensure_weights(download)
            model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=str(path))
            model.eval()
            _model = (model, preprocess, open_clip.get_tokenizer(MODEL_NAME))
    return _model


def available() -> bool:
    try:
        import open_clip  # noqa: F401
        return weights_path().exists()
    except ImportError:
        return False


def _normalize(x: np.ndarray) -> np.ndarray:
    return x / np.clip(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8, None)


def text_key(t: str) -> str:
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def _cached(conn, kind: str, refs: list[str]) -> dict[str, np.ndarray]:
    out = {}
    for i in range(0, len(refs), 500):
        chunk = refs[i:i + 500]
        q = f"SELECT ref, vector FROM embeddings WHERE kind=? AND model=? AND ref IN ({','.join('?' * len(chunk))})"
        for r in conn.execute(q, [kind, EMB_TAG, *chunk]):
            out[r["ref"]] = np.frombuffer(r["vector"], dtype=np.float32)
    return out


def _store(conn, kind: str, items: dict[str, np.ndarray]) -> None:
    conn.executemany("INSERT OR REPLACE INTO embeddings(kind, ref, model, dim, vector) VALUES(?,?,?,?,?)",
                     [(kind, k, EMB_TAG, DIM, v.astype(np.float32).tobytes()) for k, v in items.items()])
    conn.commit()


def encode_texts(texts: list[str], conn=None, batch: int = 128) -> np.ndarray:
    conn = conn or db.get_conn()
    keys = [text_key(t) for t in texts]
    have = _cached(conn, "text", list(set(keys)))
    missing = [(k, t) for k, t in dict(zip(keys, texts)).items() if k not in have]
    if missing:
        import torch
        model, _, tok = load()
        new = {}
        with torch.no_grad():
            for i in range(0, len(missing), batch):
                part = missing[i:i + batch]
                emb = model.encode_text(tok([t for _, t in part])).float().numpy()
                for (k, _), v in zip(part, _normalize(emb)):
                    new[k] = v
        _store(conn, "text", new)
        have.update(new)
    return np.stack([have[k] for k in keys]) if keys else np.zeros((0, DIM), np.float32)


def encode_images(shas_paths: list[tuple[str, Path]], conn=None, batch: int = 32) -> dict[str, np.ndarray]:
    """{sha256: vektor}; a hiányzókat kiszámolja és cache-eli."""
    conn = conn or db.get_conn()
    have = _cached(conn, "image", [s for s, _ in shas_paths])
    missing = [(s, p) for s, p in dict(shas_paths).items() if s not in have]
    if missing:
        import torch
        from PIL import Image
        model, preprocess, _ = load()
        new = {}
        with torch.no_grad():
            for i in range(0, len(missing), batch):
                part = missing[i:i + batch]
                imgs, ok = [], []
                for s, p in part:
                    try:
                        imgs.append(preprocess(Image.open(p).convert("RGB")))
                        ok.append(s)
                    except OSError as exc:
                        log.warning("kép nem olvasható %s: %s", p, exc)
                if not imgs:
                    continue
                emb = model.encode_image(torch.stack(imgs)).float().numpy()
                for s, v in zip(ok, _normalize(emb)):
                    new[s] = v
        _store(conn, "image", new)
        have.update(new)
    return have


def listing_image_vectors(conn, listing_ids: list[int]) -> dict[int, np.ndarray]:
    """Hirdetésenként a képek átlagolt (normalizált) beágyazása – csak cache-ből."""
    out: dict[int, list] = {}
    if not listing_ids:
        return {}
    for i in range(0, len(listing_ids), 500):
        chunk = listing_ids[i:i + 500]
        q = (f"SELECT i.listing_id, e.vector FROM images i JOIN images o ON o.id = COALESCE(i.dup_of, i.id) "
             f"JOIN embeddings e ON e.kind='image' AND e.ref=o.sha256 AND e.model=? "
             f"WHERE i.listing_id IN ({','.join('?' * len(chunk))}) AND i.status IN ('ok','duplicate')")
        for r in conn.execute(q, [EMB_TAG, *chunk]):
            out.setdefault(r["listing_id"], []).append(np.frombuffer(r["vector"], dtype=np.float32))
    return {k: _normalize(np.mean(v, axis=0)) for k, v in out.items()}


def embed_pending_images(conn=None, progress=None) -> int:
    conn = conn or db.get_conn()
    rows = conn.execute("SELECT DISTINCT sha256, path FROM images WHERE status='ok' AND sha256 IS NOT NULL").fetchall()
    base = settings.path("image_dir")
    pairs = [(r["sha256"], base / r["path"]) for r in rows]
    have = _cached(conn, "image", [s for s, _ in pairs])
    todo = [p for p in pairs if p[0] not in have]
    for i in range(0, len(todo), 256):
        encode_images(todo[i:i + 256], conn)
        if progress:
            progress(min(1.0, (i + 256) / max(1, len(todo))), f"{min(i + 256, len(todo))}/{len(todo)} kép beágyazva")
    return len(todo)


# --- zero-shot képi előszűrés ------------------------------------------------
PROMPTS = {
    "Herendi": ["a photo of a hand painted Herend porcelain figurine with fishnet scale pattern",
                "a photo of Herend porcelain with Rothschild bird decor",
                "a photo of Herend porcelain with Apponyi flower pattern",
                "a photo of a Herend porcelain vase with Queen Victoria butterfly decor"],
    "Zsolnay": ["a photo of a Zsolnay eosin iridescent glazed ceramic vase",
                "a photo of a Zsolnay porcelain figurine with metallic eosin glaze",
                "a photo of Zsolnay art nouveau ceramic with pierced decoration"],
    "porcelain": ["a photo of a porcelain figurine", "a photo of a porcelain vase", "a photo of fine china tableware"],
    "other": ["a photo of glass", "a photo of a book", "a photo of a postcard", "a photo of plastic toy",
              "a photo of metal jewelry", "a photo of furniture", "a photo of a painting"],
}


def zero_shot(image_vecs: np.ndarray, conn=None) -> list[dict]:
    """Minden képre: {brand: valószínűség} a promptcsoportokon (softmax, CLIP logit skála)."""
    groups = list(PROMPTS)
    texts = [t for g in groups for t in PROMPTS[g]]
    tv = encode_texts(texts, conn)
    sims = image_vecs @ tv.T * 100.0
    out = []
    for row in sims:
        g_scores = []
        idx = 0
        for g in groups:
            n = len(PROMPTS[g])
            g_scores.append(row[idx:idx + n].max())
            idx += n
        e = np.exp(np.array(g_scores) - max(g_scores))
        p = e / e.sum()
        out.append(dict(zip(groups, map(float, p))))
    return out


def visual_prefilter(conn=None, threshold: float = 0.5) -> dict:
    """A márkanév nélküli (visual_candidate) hirdetések képi rangsorolása.

    Nem azonosítás és nem eredetiség-igazolás: csak jelöli, melyiket érdemes
    kézzel/részletes oldallal ellenőrizni. A küszöb validálatlan (nincs címkézett
    képi tesztkészlet)."""
    import json
    conn = conn or db.get_conn()
    ids = [r["id"] for r in conn.execute("SELECT id FROM listings WHERE relevance='visual_candidate'")]
    vecs = listing_image_vectors(conn, ids)
    if not vecs:
        return {"candidates": len(ids), "with_images": 0, "flagged": 0}
    keys = list(vecs)
    probs = zero_shot(np.stack([vecs[k] for k in keys]), conn)
    flagged = 0
    for lid, p in zip(keys, probs):
        brand = max(("Herendi", "Zsolnay"), key=lambda b: p[b])
        match = p[brand] >= threshold
        flagged += match
        row = conn.execute("SELECT extra FROM listings WHERE id=?", (lid,)).fetchone()
        extra = json.loads(row["extra"]) if row["extra"] else {}
        extra.update({"visual_match": bool(match), "visual_brand": brand, "visual_probs": p})
        conn.execute("UPDATE listings SET extra=? WHERE id=?", (json.dumps(extra), lid))
    conn.commit()
    return {"candidates": len(ids), "with_images": len(vecs), "flagged": flagged}
