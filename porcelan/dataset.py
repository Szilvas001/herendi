"""Tanítóadat összeállítása a `price_records` táblából.

Szabályok:
- Az ártípus explicit. Célváltozó-alap piaconként: ha van elég realizált ár
  (realized_sale / auction_hammer / auction_final_bid), azt használjuk; ha nincs,
  a modell kínálati áron (asking_active) tanul, és a manifest ezt jelzi.
  Futó aukció aktuális licitje és kikiáltási ára NEM célváltozó.
- A célváltozó a piac saját pénznemében van (HU: HUF, US: USD). Az amerikai
  érték nem a magyar becslés átváltása.
- Duplikátum: azonos normalizált cím + eladó (újrahirdetés) → egy sor (a legfrissebb).
- Csoport: újrahirdetés, közös kép (sha256 / pHash) vagy közel azonos cím
  ugyanabba a csoportba kerül; a felosztás csoportszintű.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import db, images, settings, text

REALIZED_TYPES = ("realized_sale", "auction_hammer", "auction_final_bid")
ASKING_TYPES = ("asking_active",)
MARKETS = ("HU", "US")
CURRENCY = {"HU": "HUF", "US": "USD"}
MIN_REALIZED_FOR_BASIS = 200


@dataclass
class Dataset:
    df: pd.DataFrame
    basis: dict          # piac -> 'realized' | 'asking'
    report: dict


def _to_native(row, fx) -> float | None:
    cur = (row["currency"] or "").upper()
    target = CURRENCY[row["market"]]
    amount = float(row["amount"])
    if row["price_type"] == "auction_hammer" and row["buyer_premium_rate"]:
        amount *= 1 + float(row["buyer_premium_rate"])   # vevő által fizetett ár
    if cur == target:
        return amount
    rates = {"HUF": 1.0, "USD": fx["huf_per_usd"], "EUR": fx["huf_per_eur"]}
    if cur not in rates:
        return None
    return amount * rates[cur] / rates[target]


def load_records(conn) -> pd.DataFrame:
    rows = conn.execute("SELECT p.*, l.description AS l_desc, l.seller AS seller, l.extra AS l_extra "
                        "FROM price_records p LEFT JOIN listings l ON l.id=p.listing_id "
                        "WHERE p.market IN ('HU','US')").fetchall()
    return pd.DataFrame([dict(r) for r in rows])


def build(conn=None, include_general: bool = True) -> Dataset:
    """Tanítóadat. `corpus` oszlop: herend_zsolnay (a termék célpopulációja, ezen
    értékelünk) és general (általános porcelán/kerámia, csak előtanításra)."""
    conn = conn or db.get_conn()
    fx = settings.get("fx")
    raw = load_records(conn)
    report = {"raw_records": int(len(raw)), "by_type": {}, "dropped": {}}
    if raw.empty:
        return Dataset(raw, {}, report)
    raw["corpus"] = raw["corpus"].fillna("herend_zsolnay")
    if not include_general:
        raw = raw[raw.corpus == "herend_zsolnay"]
    report["by_type"] = {f"{c}/{m}/{t}": int(n) for (c, m, t), n in
                         raw.groupby(["corpus", "market", "price_type"]).size().items()}

    basis = {}
    parts = []
    hz = raw[raw.corpus == "herend_zsolnay"]
    for market in MARKETS:
        sub = hz[hz.market == market]
        realized = sub[sub.price_type.isin(REALIZED_TYPES)]
        if len(realized) >= MIN_REALIZED_FOR_BASIS:
            basis[market] = "realized"
            parts.append(realized)
        else:
            asking = sub[sub.price_type.isin(ASKING_TYPES)]
            if len(asking):
                basis[market] = "asking"
                parts.append(asking)
            report.setdefault("notes", []).append(
                f"{market}: {len(realized)} realizált Herendi/Zsolnay ár < {MIN_REALIZED_FOR_BASIS} "
                f"→ kínálati áron tanul (kísérleti)")
    gen = raw[(raw.corpus == "general") & raw.price_type.isin(REALIZED_TYPES + ASKING_TYPES)]
    if len(gen):
        parts.append(gen)
    df = pd.concat(parts, ignore_index=True) if parts else raw.iloc[0:0]

    df["y_native"] = [_to_native(r, fx) for r in df.to_dict("records")]
    before = len(df)
    df = df[df.y_native.notna() & (df.y_native > 0)]
    report["dropped"]["no_price_or_currency"] = before - len(df)
    # Irreális értékek (pl. 1 Ft-os "jelképes" ár vagy elírás) – piaconkénti korlát.
    lo = {"HU": 500, "US": 5}
    hi = {"HU": 20_000_000, "US": 60_000}
    mask = [(lo[m] <= y <= hi[m]) for m, y in zip(df.market, df.y_native)]
    report["dropped"]["out_of_range"] = int(len(df) - sum(mask))
    df = df[mask].copy()

    df["description"] = df["description"].fillna(df["l_desc"]).fillna("")
    df["observed_at"] = pd.to_datetime(df["observed_at"], utc=True, format="ISO8601")
    # Újrahirdetések: dedup_key + piac szerint a legfrissebb marad.
    df = df.sort_values("observed_at")
    before = len(df)
    df = df.drop_duplicates(subset=["market", "dedup_key"], keep="last")
    report["dropped"]["relisting_duplicates"] = before - len(df)

    # Jellemzők újraszámítása egységes kódból (a tárolt mezők importkori állapotot tükrözhetnek).
    feats = [text.extract(t or "", d or "") for t, d in zip(df.title, df.description)]
    for key in ("brand", "object_type", "decor", "size_cm", "pieces", "condition", "damage_flags",
                "mark_flags", "suspect_flags", "canonical_en"):
        df[key] = [f[key] for f in feats]
    fake = [bool(f["fake_hits"] or f["non_item_hits"]) for f in feats]
    report["dropped"]["fake_or_non_item"] = int(sum(fake))
    df = df[[not x for x in fake]]
    # a márka nélküli "Herendi/Zsolnay" rekord az általános korpuszba kerül
    hzb = df.brand.isin([text.BRAND_HEREND, text.BRAND_ZSOLNAY])
    df.loc[(df.corpus == "herend_zsolnay") & ~hzb, "corpus"] = "general"
    df.loc[(df.corpus == "general") & hzb & df.market.map(lambda m: m in basis), "corpus"] = "herend_zsolnay"
    # a HZ-korpuszban csak a piac célváltozó-alapjának megfelelő ártípus marad
    keep = [(c != "herend_zsolnay") or (basis.get(m) == "realized" and t in REALIZED_TYPES)
            or (basis.get(m) == "asking" and t in ASKING_TYPES)
            for c, m, t in zip(df.corpus, df.market, df.price_type)]
    df = df[keep].reset_index(drop=True)
    df["group"] = assign_groups(conn, df)
    df["y_log"] = np.log(df["y_native"].astype(float))
    df["basis"] = df.market.map(basis)
    df["has_image"] = _image_flags(conn, df)
    report["rows"] = int(len(df))
    report["groups"] = int(df.group.nunique())
    report["by_corpus_market"] = {f"{c}/{m}": int(n) for (c, m), n in df.groupby(["corpus", "market"]).size().items()}
    report["by_market"] = {m: int(n) for m, n in df[df.corpus == "herend_zsolnay"].market.value_counts().items()}
    report["by_market_brand"] = {f"{m}/{b}": int(n) for (m, b), n in
                                 df[df.corpus == "herend_zsolnay"].groupby(["market", "brand"]).size().items()}
    report["observation_days"] = sorted({d.date().isoformat() for d in df.observed_at})[-60:]
    report["with_images"] = int(df[df.corpus == "herend_zsolnay"].has_image.sum())
    report["general_rows"] = int((df.corpus == "general").sum())
    report["general_with_images"] = int(df[df.corpus == "general"].has_image.sum())
    return Dataset(df, basis, report)


def _image_flags(conn, df: pd.DataFrame) -> list[bool]:
    with_l = {r[0] for r in conn.execute("SELECT DISTINCT listing_id FROM images WHERE status IN ('ok','duplicate') "
                                         "AND listing_id IS NOT NULL")}
    with_r = {r[0] for r in conn.execute("SELECT DISTINCT price_record_id FROM images WHERE status IN ('ok','duplicate') "
                                         "AND price_record_id IS NOT NULL")}
    out = []
    for lid, rid in zip(df.listing_id, df["id"]):
        ok = (lid is not None and lid == lid and int(lid) in with_l) or (rid is not None and rid == rid and int(rid) in with_r)
        out.append(bool(ok))
    return out


class _UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, a):
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


_PRIME = (1 << 61) - 1
_rng = np.random.default_rng(12345)
_MH_A = _rng.integers(1, _PRIME - 1, size=64, dtype=np.int64)
_MH_B = _rng.integers(0, _PRIME - 1, size=64, dtype=np.int64)


def _minhash(tokens: set[str]) -> np.ndarray:
    import zlib
    if not tokens:
        return np.zeros(64, dtype=np.int64)
    h = np.array([zlib.crc32(t.encode()) for t in tokens], dtype=np.int64)
    # (a*h + b) mod p, 64 független permutáció; object-aritmetika nélkül: a és h < 2^32 ... p ~ 2^61
    vals = (np.outer(_MH_A % (1 << 29), h) + _MH_B[:, None]) % _PRIME
    return vals.min(axis=1)


def assign_groups(conn, df: pd.DataFrame, jaccard: float = 0.85) -> list[str]:
    """Csoportazonosító: újrahirdetés, közös kép vagy közel azonos cím összevonva.

    Skálázható: a közel azonos címeket MinHash-LSH (16 sáv × 4 sor), a közel
    azonos képeket pHash sáv-index jelöli ki; csak a jelölt párokat ellenőrizzük
    pontosan. Százezres adathalmazon is lineáris közeli."""
    n = len(df)
    uf = _UF(n)
    by_key: dict = {}
    for i, k in enumerate(df.dedup_key):
        if k in by_key:
            uf.union(i, by_key[k])
        by_key.setdefault(k, i)
    # közös kép (bájtazonos vagy pHash-közeli)
    img_owner: dict = {}
    band_owner: dict = {}
    img_rows = []
    lids = list(df.listing_id) if "listing_id" in df else [None] * n
    rids = list(df["id"]) if "id" in df else [None] * n
    for i in range(n):
        lid, rid = lids[i], rids[i]
        if lid is not None and lid == lid:
            q, arg = "SELECT sha256, phash FROM images WHERE listing_id=? AND sha256 IS NOT NULL", int(lid)
        elif rid is not None and rid == rid:
            q, arg = "SELECT sha256, phash FROM images WHERE price_record_id=? AND sha256 IS NOT NULL", int(rid)
        else:
            continue
        for r in conn.execute(q, (arg,)):
            img_rows.append((i, r["sha256"], r["phash"]))
    for i, sha, ph in img_rows:
        if sha in img_owner:
            uf.union(i, img_owner[sha])
        img_owner.setdefault(sha, i)
        if ph:
            for b, val in images.bands(ph):
                for j, ph2 in band_owner.get((b, val), []):
                    if j != i and images.hamming(ph, ph2) <= images.PHASH_DUP_BITS:
                        uf.union(i, j)
                lst = band_owner.setdefault((b, val), [])
                if len(lst) < 200:
                    lst.append((i, ph))
    # közel azonos cím: MinHash-LSH piacon és márkán belül
    toks = [text.title_tokens(t) for t in df.title]
    brands = [b if isinstance(b, str) else "" for b in df.brand]
    markets = list(df.market)
    buckets: dict = {}
    for i in range(n):
        if len(toks[i]) < 2:
            continue
        sig = _minhash(toks[i])
        for b in range(16):
            key = (markets[i], brands[i], b, tuple(sig[b * 4:(b + 1) * 4]))
            buckets.setdefault(key, []).append(i)
    checked = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        members = members[:300]    # óriásvödör (nagyon gyakori cím) esetén korlát
        for a_i in range(len(members)):
            for b_i in range(a_i + 1, len(members)):
                a, b = members[a_i], members[b_i]
                if (a, b) in checked:
                    continue
                checked.add((a, b))
                ta, tb = toks[a], toks[b]
                inter = len(ta & tb)
                if inter and inter / len(ta | tb) >= jaccard:
                    uf.union(a, b)
    return [f"g{uf.find(i)}" for i in range(n)]


def split(df: pd.DataFrame, seed: int = 42, val_frac: float = 0.15, test_frac: float = 0.15) -> tuple[pd.Series, dict]:
    """'train' / 'val' / 'test' a Herendi/Zsolnay korpuszon; az általános korpusz
    'pretrain', kivéve ha csoportja (közös kép / közel azonos cím) a validációs vagy
    teszthalmazba esik – akkor 'excluded' (szivárgásvédelem).

    Ha a megfigyelések legalább 30 napot fednek le, a teszthalmaz az időben
    legkésőbbi csoportokból áll (időbeli teszt); különben csoportszintű
    véletlen felosztás, és ezt a riport jelzi."""
    info = {"seed": seed}
    corpus = df["corpus"] if "corpus" in df else pd.Series("herend_zsolnay", index=df.index)
    hz = df[corpus == "herend_zsolnay"]
    span = (hz.observed_at.max() - hz.observed_at.min()).days if len(hz) else 0
    groups = hz.groupby("group").observed_at.max().sort_values()
    rng = np.random.default_rng(seed)
    labels = pd.Series("train", index=df.index)
    if span >= 30:
        n_test = int(round(len(groups) * test_frac))
        test_groups = set(groups.index[-n_test:])
        rest = [g for g in groups.index if g not in test_groups]
        info["test"] = f"időbeli: a legkésőbbi {n_test} csoport ({groups.iloc[-n_test]:%Y-%m-%d} után)"
    else:
        order = list(groups.index)
        rng.shuffle(order)
        n_test = int(round(len(order) * test_frac))
        test_groups = set(order[:n_test])
        rest = order[n_test:]
        info["test"] = (f"csoportszintű véletlen (a megfigyelések csak {span} napot fednek le; "
                        f"időbeli teszt nem lehetséges)")
    rest = list(rest)
    rng.shuffle(rest)
    n_val = int(round(len(groups) * val_frac))
    val_groups = set(rest[:n_val])
    labels[df.group.isin(test_groups)] = "test"
    labels[df.group.isin(val_groups)] = "val"
    gen = corpus == "general"
    labels[gen] = "pretrain"
    labels[gen & df.group.isin(test_groups | val_groups)] = "excluded"
    labels[(~gen) & (labels == "pretrain")] = "train"
    info["counts"] = {k: int(v) for k, v in labels.value_counts().items()}
    # szivárgás-ellenőrzés
    for a, b in (("train", "val"), ("train", "test"), ("val", "test"), ("pretrain", "val"), ("pretrain", "test")):
        assert not (set(df.group[labels == a]) & set(df.group[labels == b])), "csoport-szivárgás"
    return labels, info


def fingerprint(df: pd.DataFrame) -> str:
    cols = ["source", "source_ref", "market", "price_type", "y_native", "observed_at", "title"]
    payload = df[cols].astype(str).sort_values(cols).to_csv(index=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def export(df: pd.DataFrame, path, labels=None) -> None:
    out = df[["source", "source_ref", "market", "price_type", "amount", "currency", "y_native", "observed_at",
              "title", "brand", "object_type", "decor", "size_cm", "pieces", "condition", "url", "group",
              "corpus"]].copy()
    if labels is not None:
        out["split"] = labels
    out.to_csv(path, index=False, compression="gzip")


def summary_json(ds: Dataset) -> str:
    return json.dumps(ds.report, ensure_ascii=False, indent=1, default=str)
