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


def build(conn=None) -> Dataset:
    conn = conn or db.get_conn()
    fx = settings.get("fx")
    raw = load_records(conn)
    report = {"raw_records": int(len(raw)), "by_type": {}, "dropped": {}}
    if raw.empty:
        return Dataset(raw, {}, report)
    report["by_type"] = {f"{m}/{t}": int(n) for (m, t), n in raw.groupby(["market", "price_type"]).size().items()}

    basis = {}
    parts = []
    for market in MARKETS:
        sub = raw[raw.market == market]
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
                f"{market}: {len(realized)} realizált ár < {MIN_REALIZED_FOR_BASIS} → kínálati áron tanul (kísérleti)")
    df = pd.concat(parts, ignore_index=True) if parts else raw.iloc[0:0]

    df["y_native"] = [_to_native(r, fx) for _, r in df.iterrows()]
    before = len(df)
    df = df[df.y_native.notna() & (df.y_native > 0)]
    report["dropped"]["no_price_or_currency"] = before - len(df)
    df = df[df.brand.isin([text.BRAND_HEREND, text.BRAND_ZSOLNAY])]
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
    df = df.reset_index(drop=True)
    df["group"] = assign_groups(conn, df)
    df["y_log"] = np.log(df["y_native"].astype(float))
    df["basis"] = df.market.map(basis)
    report["rows"] = int(len(df))
    report["groups"] = int(df.group.nunique())
    report["by_market"] = {m: int(n) for m, n in df.market.value_counts().items()}
    report["by_market_brand"] = {f"{m}/{b}": int(n) for (m, b), n in df.groupby(["market", "brand"]).size().items()}
    report["observation_days"] = sorted({d.date().isoformat() for d in df.observed_at})
    report["with_images"] = int(sum(1 for x in df.listing_id if x == x and x is not None and _has_image(conn, x)))
    return Dataset(df, basis, report)


def _has_image(conn, listing_id) -> bool:
    return conn.execute("SELECT 1 FROM images WHERE listing_id=? AND status IN ('ok','duplicate') LIMIT 1",
                        (int(listing_id),)).fetchone() is not None


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


def assign_groups(conn, df: pd.DataFrame, jaccard: float = 0.85) -> list[str]:
    """Csoportazonosító: újrahirdetés, közös kép vagy közel azonos cím összevonva."""
    n = len(df)
    uf = _UF(n)
    by_key: dict = {}
    for i, k in enumerate(df.dedup_key):
        if k in by_key:
            uf.union(i, by_key[k])
        by_key.setdefault(k, i)
    # közös kép (bájtazonos vagy pHash-közeli) – csak hirdetéshez kötött rekordoknál
    img_owner: dict = {}
    phashes: list[tuple[str, int]] = []
    for i, lid in enumerate(df.listing_id):
        if lid is None or lid != lid:
            continue
        for r in conn.execute("SELECT sha256, phash FROM images WHERE listing_id=? AND sha256 IS NOT NULL",
                              (int(lid),)):
            if r["sha256"] in img_owner:
                uf.union(i, img_owner[r["sha256"]])
            img_owner.setdefault(r["sha256"], i)
            if r["phash"]:
                phashes.append((r["phash"], i))
    for a in range(len(phashes)):
        for b in range(a + 1, len(phashes)):
            if phashes[a][1] != phashes[b][1] and images.hamming(phashes[a][0], phashes[b][0]) <= images.PHASH_DUP_BITS:
                uf.union(phashes[a][1], phashes[b][1])
    # közel azonos cím (márkán és piacon belül)
    toks = [text.title_tokens(t) for t in df.title]
    for (_, _), idx in df.groupby(["market", "brand"]).indices.items():
        idx = list(idx)
        for ai in range(len(idx)):
            ta = toks[idx[ai]]
            if len(ta) < 2:
                continue
            for bi in range(ai + 1, len(idx)):
                tb = toks[idx[bi]]
                if len(tb) < 2:
                    continue
                inter = len(ta & tb)
                if inter and inter / len(ta | tb) >= jaccard:
                    uf.union(idx[ai], idx[bi])
    return [f"g{uf.find(i)}" for i in range(n)]


def split(df: pd.DataFrame, seed: int = 42, val_frac: float = 0.15, test_frac: float = 0.15) -> tuple[pd.Series, dict]:
    """'train' / 'val' / 'test' címke soronként + leírás.

    Ha a megfigyelések legalább 30 napot fednek le, a teszthalmaz az időben
    legkésőbbi csoportokból áll (időbeli teszt); különben csoportszintű
    véletlen felosztás, és ezt a riport jelzi."""
    info = {"seed": seed}
    span = (df.observed_at.max() - df.observed_at.min()).days if len(df) else 0
    groups = df.groupby("group").observed_at.max().sort_values()
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
    info["counts"] = {k: int(v) for k, v in labels.value_counts().items()}
    # szivárgás-ellenőrzés
    for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
        assert not (set(df.group[labels == a]) & set(df.group[labels == b])), "csoport-szivárgás"
    return labels, info


def fingerprint(df: pd.DataFrame) -> str:
    cols = ["source", "source_ref", "market", "price_type", "y_native", "observed_at", "title"]
    payload = df[cols].astype(str).sort_values(cols).to_csv(index=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def export(df: pd.DataFrame, path, labels=None) -> None:
    out = df[["source", "source_ref", "market", "price_type", "amount", "currency", "y_native", "observed_at",
              "title", "brand", "object_type", "decor", "size_cm", "pieces", "condition", "url", "group"]].copy()
    if labels is not None:
        out["split"] = labels
    out.to_csv(path, index=False, compression="gzip")


def summary_json(ds: Dataset) -> str:
    return json.dumps(ds.report, ensure_ascii=False, indent=1, default=str)
