"""Jellemző-pipeline: strukturált + szöveg (TF-IDF) + CLIP szöveg + CLIP kép.

A pipeline a tanítóhalmazon illesztődik, és a modellverzióval együtt mentődik,
így a dashboard-becslés ugyanazt a transzformációt használja, mint a tanítás.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from . import text, vision

DECOR_NAMES = [d[0] for d in text.DECORS]
OBJECT_CODES = [c for c, _, _ in text.OBJECT_TYPES] + ["other"]
CONDITIONS = ["hibatlan", "ismeretlen", "serult", "javitott"]
MARKS = list(text.MARK_CUES)
DAMAGES = list(text.DAMAGE_CUES)
BRANDS = [text.BRAND_HEREND, text.BRAND_ZSOLNAY]
T0 = pd.Timestamp("2020-01-01", tz="UTC")


def _s(val) -> str:
    return val if isinstance(val, str) else ""


def _multi(val, names) -> list[float]:
    s = _s(val)
    return [1.0 if n in s else 0.0 for n in names]


def structured(df: pd.DataFrame) -> np.ndarray:
    rows = []
    for _, r in df.iterrows():
        size = r.get("size_cm")
        pcs = r.get("pieces")
        size_ok = size is not None and size == size
        pcs_ok = pcs is not None and pcs == pcs
        obs = r.get("observed_at")
        years = ((pd.Timestamp(obs) - T0).days / 365.25) if obs is not None and obs == obs else 6.7
        rows.append(
            [1.0 if r.get("brand") == b else 0.0 for b in BRANDS]
            + [1.0 if r.get("object_type") == c else 0.0 for c in OBJECT_CODES]
            + _multi(r.get("decor"), DECOR_NAMES)
            + [1.0 if r.get("condition") == c else 0.0 for c in CONDITIONS]
            + _multi(r.get("mark_flags"), MARKS)
            + _multi(r.get("damage_flags"), DAMAGES)
            + [1.0 if _s(r.get("suspect_flags")) else 0.0]
            + [np.log1p(float(size)) if size_ok else 0.0, 1.0 if size_ok else 0.0,
               np.log1p(float(pcs)) if pcs_ok else 0.0, 1.0 if pcs_ok else 0.0,
               1.0 if _s(r.get("description")) else 0.0, (years - 6.7)])
    return np.asarray(rows, dtype=np.float32)


def structured_names() -> list[str]:
    return ([f"brand={b}" for b in BRANDS] + [f"type={c}" for c in OBJECT_CODES] + [f"decor={d}" for d in DECOR_NAMES]
            + [f"cond={c}" for c in CONDITIONS] + [f"mark={m}" for m in MARKS] + [f"dmg={d}" for d in DAMAGES]
            + ["suspect", "log_size", "has_size", "log_pieces", "has_pieces", "has_description", "years_since_2020_centered"])


def _doc(df: pd.DataFrame) -> list[str]:
    return [text.norm(f"{t} {(d or '')[:600]}") for t, d in zip(df.title, df.description.fillna(""))]


class FeaturePipeline:
    def __init__(self, svd_dim: int = 96, use_clip: bool = True):
        self.svd_dim = svd_dim
        self.use_clip = use_clip
        self.tfidf = None
        self.svd = None
        self.struct_mean = None
        self.struct_std = None

    def fit(self, df: pd.DataFrame, conn=None) -> "FeaturePipeline":
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, max_features=40000,
                                     sublinear_tf=True)
        x = self.tfidf.fit_transform(_doc(df))
        k = max(2, min(self.svd_dim, x.shape[1] - 1, x.shape[0] - 1))
        self.svd = TruncatedSVD(n_components=k, random_state=0).fit(x)
        s = structured(df)
        self.struct_mean = s.mean(axis=0)
        std = s.std(axis=0)
        # a tanítóhalmazon (közel) konstans jellemzőt nem skálázzuk fel
        self.struct_std = np.where(std < 1e-2, 1.0, std).astype(np.float32)
        return self

    def transform(self, df: pd.DataFrame, conn=None) -> dict[str, np.ndarray]:
        blocks = {}
        blocks["struct"] = ((structured(df) - self.struct_mean) / self.struct_std).astype(np.float32)
        blocks["tfidf"] = self.svd.transform(self.tfidf.transform(_doc(df))).astype(np.float32)
        n = len(df)
        if self.use_clip:
            blocks["clip_canon"] = vision.encode_texts(list(df.canonical_en.fillna("a porcelain object")), conn)
            # angol címek (US) közvetlenül; magyar címeknél a kanonikus leírás a híd
            blocks["clip_title"] = vision.encode_texts([str(t)[:200] for t in df.title], conn)
            ids = [int(x) for x in df.get("listing_id", pd.Series([None] * n)) if x is not None and x == x]
            img = vision.listing_image_vectors(conn, ids) if conn is not None and ids else {}
            mat = np.zeros((n, vision.DIM), np.float32)
            mask = np.zeros((n, 1), np.float32)
            for i, lid in enumerate(df.get("listing_id", pd.Series([None] * n))):
                if lid is not None and lid == lid and int(lid) in img:
                    mat[i] = img[int(lid)]
                    mask[i] = 1.0
            blocks["clip_image"] = mat
            blocks["image_mask"] = mask
        return blocks


def concat(blocks: dict[str, np.ndarray], keys: list[str]) -> np.ndarray:
    return np.concatenate([blocks[k] for k in keys], axis=1).astype(np.float32)
