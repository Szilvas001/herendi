"""Cikkszám-szintű piaci ár: pontos termék → pontos ár, mért ±10%-os pontossággal.

Egy adott termék piaci ára = ugyanannak a terméknek (gyártó + formaszám + mintakód)
a piaci eladásaiból számolt tipikus ár, állapotra korrigálva. A becslés log-skálán,
normál–normál (empirikus Bayes) kombináció:

  bizonyíték                          szórás
  ───────────────────────────────────  ─────────────────────────────────────
  azonos cikkszám eladásai (n db)      σ  (cikkszámon belüli piaci szórás)
  azonos formaszám, más minta          √(σ² + σ_minta²)
  kép+szöveg modell (előzetes becslés) τ  (a neurális modell saját bizonytalansága)

A σ, σ_minta és az állapot-korrekció az adatból becsült (legalább két eladással
rendelkező cikkszámokból), nem feltételezett érték. A kimenet: piaci ár, 80%-os
intervallum, és P(|hiba| ≤ 10%) – ebből dől el, hogy a rendszer „pontos árat”
mond-e (ha ≥ 90%, és ezt a kihagyásos validáció is alátámasztja) vagy csak sávot.

Értékelés (evaluate): minden cikkszámmal azonosított rekordra úgy becsülünk, hogy
a saját csoportját (újrahirdetés, közös kép, azonos cím) kihagyjuk, és – ha a
megfigyelések időben szétszóródnak – csak korábbi eladásokat használunk.
Mérőszámok: MdAPE, a ±10%-on belüli arány, 90. percentilis hiba, a „pontos”
jelzésű becslések aránya és azokon a ±10%-on belüli arány.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import dataset, db, settings

LOG_10PCT = math.log(1.10)
Z80 = 1.2816


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def prob_within(sd: float, tol: float = 0.10) -> float:
    """P(|exp(e)-1| ≤ tol), ha a log-hiba e ~ N(0, sd²)."""
    if sd <= 0:
        return 1.0
    return _phi(math.log(1 + tol) / sd) - _phi(math.log(1 - tol) / sd)


def _robust_sd(x: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(x - np.median(x)))) if len(x) else float("nan")


class SkuPricer:
    """Paraméterek becslése a tárolt, azonosított ár-rekordokból; becslés adott termékre."""

    def __init__(self, df: pd.DataFrame):
        """df: dataset.build() sorai + sku_key, form_key, pattern_code, y_log, market, condition, group."""
        self.df = df[df.sku_key.notna()].copy()
        self.params = self._fit_params()

    # -- paraméterek -----------------------------------------------------------
    def _fit_params(self) -> dict:
        d = self.df
        p = {"n_records": int(len(d)), "sigma_by_market": {}, "sigma_pattern": {}, "condition_effect": {}}
        for m, g in d.groupby("market"):
            # cikkszámon belüli szórás: legalább 2 eladásos cikkszámok, csoportonként 1 rekord
            one = g.drop_duplicates("group")
            res, npairs = [], 0
            for _, gg in one.groupby("sku_key"):
                if len(gg) >= 2:
                    res.extend(list(gg.y_log - gg.y_log.median()))
                    npairs += len(gg)
            sd = _robust_sd(np.array(res)) * math.sqrt(1.5) if len(res) >= 6 else None
            p["sigma_by_market"][m] = {"sigma": sd, "n": npairs,
                                       "note": None if sd else "kevés ismételt eladás; alapérték 0.35"}
            # azonos formaszám, eltérő minta: a mintahatás szórása
            fres = []
            for _, gg in one.groupby("form_key"):
                meds = gg.groupby("sku_key").y_log.median()
                if len(meds) >= 2:
                    fres.extend(list(meds - meds.median()))
            p["sigma_pattern"][m] = _robust_sd(np.array(fres)) if len(fres) >= 6 else None
            # állapot-korrekció: a cikkszám mediánjához képest
            eff = {}
            for cond, gg in one.groupby("condition"):
                devs = []
                for key, row in gg.groupby("sku_key"):
                    rest = one[(one.sku_key == key) & (one.condition != cond)]
                    if len(rest):
                        devs.extend(list(row.y_log - rest.y_log.median()))
                eff[cond] = {"log_effect": float(np.median(devs)) if len(devs) >= 5 else None, "n": len(devs)}
            p["condition_effect"][m] = eff
        return p

    def sigma(self, market: str) -> float:
        s = (self.params["sigma_by_market"].get(market) or {}).get("sigma")
        return s if s and s > 0 else 0.35

    def sigma_pattern(self, market: str) -> float:
        s = self.params["sigma_pattern"].get(market)
        return s if s and s > 0 else 0.5

    def cond_adj(self, market: str, cond: str | None) -> float:
        e = ((self.params["condition_effect"].get(market) or {}).get(cond or "ismeretlen") or {}).get("log_effect")
        return e or 0.0

    # -- becslés ------------------------------------------------------------------
    def estimate(self, market: str, sku_key: str | None, condition: str | None,
                 prior_mu: float | None = None, prior_sd: float | None = None,
                 exclude_groups: set | None = None, before=None, exclude_refs: set | None = None) -> dict:
        """Piaci ár (log-skálán kombinálva) egy konkrét termékre.

        before: csak az ennél korábbi eladások (időrendi értékelés)."""
        d = self.df[self.df.market == market]
        if exclude_refs:
            # a becsült hirdetés saját rekordja és annak újrahirdetései (azonos eladási csoport) kimaradnak
            own = set(self.df[self.df.source_ref.astype(str).isin({str(x) for x in exclude_refs})].group)
            d = d[~d.group.isin(own)]
        if exclude_groups:
            d = d[~d.group.isin(exclude_groups)]
        if before is not None:
            d = d[d.observed_at < before]
        sig = self.sigma(market)
        terms = []            # (érték, variancia, címke)
        exact = pd.DataFrame()
        if sku_key and not sku_key.endswith("|-"):
            exact = d[d.sku_key == sku_key].drop_duplicates("group")
            for _, r in exact.iterrows():
                terms.append((r.y_log - self.cond_adj(market, r.condition), sig ** 2, "azonos cikkszám"))
        form_key = "|".join(sku_key.split("|")[:2]) if sku_key else None
        same_form = pd.DataFrame()
        if form_key:
            same_form = d[(d.form_key == form_key) & (d.sku_key != sku_key)].drop_duplicates("group")
            sp = self.sigma_pattern(market)
            for _, r in same_form.iterrows():
                terms.append((r.y_log - self.cond_adj(market, r.condition), sig ** 2 + sp ** 2, "azonos formaszám"))
        if prior_mu is not None and prior_sd:
            terms.append((prior_mu, prior_sd ** 2, "kép+szöveg modell"))
        if not terms:
            return {"mu": None, "n_exact": 0, "n_form": 0}
        w = np.array([1 / v for _, v, _ in terms])
        vals = np.array([x for x, _, _ in terms])
        mu = float((w * vals).sum() / w.sum()) + self.cond_adj(market, condition)
        post_sd = math.sqrt(1 / w.sum())
        # a "valódi piaci ár" = a termék tipikus ára → a becslés hibája a post_sd
        return {"mu": mu, "sd": post_sd, "q10": mu - Z80 * post_sd, "q90": mu + Z80 * post_sd,
                "p_within_10": prob_within(post_sd), "n_exact": int(len(exact)), "n_form": int(len(same_form)),
                "sigma_market": sig, "evidence": sorted({t for _, _, t in terms})}


def load_frame(conn=None) -> pd.DataFrame:
    """Azonosított (formaszám) ár-rekordok a tanítóadat-szabályok szerint."""
    conn = conn or db.get_conn()
    ds = dataset.build(conn)
    df = ds.df
    ids = {r["id"]: r for r in conn.execute("SELECT id, sku_key, form_no, pattern_code, id_confidence, id_basis "
                                            "FROM price_records WHERE sku_key IS NOT NULL")}
    df["sku_key"] = [ids[i]["sku_key"] if i in ids else None for i in df["id"]]
    df["pattern_code"] = [ids[i]["pattern_code"] if i in ids else None for i in df["id"]]
    df["id_confidence"] = [ids[i]["id_confidence"] if i in ids else None for i in df["id"]]
    df["form_key"] = [("|".join(k.split("|")[:2]) if isinstance(k, str) else None) for k in df.sku_key]
    df["sku_key"] = [k if isinstance(k, str) else None for k in df.sku_key]
    df["pattern_code"] = [k if isinstance(k, str) else None for k in df.pattern_code]
    # Cikkszám-szinten a "közel azonos cím" NEM újrahirdetés: ugyanazon termék különböző eladásainak
    # címe is azonos. Itt csak a valódi újrahirdetés (azonos normalizált cím + eladó) és a közös kép
    # (bájtazonos / pHash-közeli) számít ugyanannak az eladásnak.
    df["group"] = _sale_groups(conn, df)
    df.attrs["basis"] = ds.basis
    return df


def _sale_groups(conn, df: pd.DataFrame) -> list[str]:
    from .dataset import _UF
    from . import images
    n = len(df)
    uf = _UF(n)
    first: dict = {}
    for i, k in enumerate(df.dedup_key):
        if k in first:
            uf.union(i, first[k])
        first.setdefault(k, i)
    owner: dict = {}
    bands: dict = {}
    for i, (lid, rid) in enumerate(zip(df.listing_id, df["id"])):
        if lid is not None and lid == lid:
            rows = conn.execute("SELECT sha256, phash FROM images WHERE listing_id=? AND sha256 IS NOT NULL", (int(lid),))
        elif rid is not None and rid == rid:
            rows = conn.execute("SELECT sha256, phash FROM images WHERE price_record_id=? AND sha256 IS NOT NULL",
                                (int(rid),))
        else:
            continue
        for r in rows:
            if r["sha256"] in owner:
                uf.union(i, owner[r["sha256"]])
            owner.setdefault(r["sha256"], i)
            if r["phash"]:
                for b in images.bands(r["phash"]):
                    for j, ph in bands.get(b, []):
                        if j != i and images.hamming(ph, r["phash"]) <= images.PHASH_DUP_BITS:
                            uf.union(i, j)
                    bands.setdefault(b, []).append((i, r["phash"]))
    return [f"s{uf.find(i)}" for i in range(n)]


def evaluate(conn=None, prior: dict | None = None, min_p: float = 0.9) -> dict:
    """Kihagyásos (csoportonkénti; ha lehet, időrendi) értékelés a cikkszámmal azonosított rekordokon.

    prior: {rekord id: (mu, sd)} – a kép+szöveg modell mintán kívüli becslése (ha van)."""
    conn = conn or db.get_conn()
    df = load_frame(conn)
    pr = SkuPricer(df)
    d = pr.df
    span_days = (d.observed_at.max() - d.observed_at.min()).days if len(d) else 0
    temporal = span_days >= 30
    rows = []
    for _, r in d.iterrows():
        mu0, sd0 = (prior or {}).get(r["id"], (None, None))
        est = pr.estimate(r.market, r.sku_key if r.pattern_code else r.form_key + "|-", r.condition, mu0, sd0,
                          exclude_groups={r.group}, before=r.observed_at if temporal else None)
        if est["mu"] is None or (est["n_exact"] == 0 and est["n_form"] == 0):
            continue
        pred, actual = math.exp(est["mu"]), math.exp(r.y_log)
        rows.append({"market": r.market, "brand": r.brand, "sku_key": r.sku_key, "n_exact": est["n_exact"],
                     "n_form": est["n_form"], "ape": abs(pred - actual) / actual, "p_within_10": est["p_within_10"],
                     "price_type": r.price_type})
    res = {"records_identified": int(len(d)), "evaluated": len(rows), "temporal": temporal,
           "params": pr.params, "target_basis": df.attrs.get("basis"), "by_market": {}}
    ev = pd.DataFrame(rows)
    for m, g in (ev.groupby("market") if len(ev) else []):
        ape = g.ape.values
        sure = g[g.p_within_10 >= min_p]
        res["by_market"][m] = {
            "n": int(len(g)), "mdape": float(np.median(ape)), "within_10pct": float(np.mean(ape <= 0.10)),
            "p90_ape": float(np.quantile(ape, 0.9)),
            "exact_sku_rows": int((g.n_exact > 0).sum()),
            "precise_share": float(len(sure) / len(g)),
            "precise_within_10pct": float(np.mean(sure.ape <= 0.10)) if len(sure) else None,
            "mean_predicted_p_within_10": float(g.p_within_10.mean()),
        }
    res["market_price_curve"] = market_price_curve(pr)
    db.set_meta(conn, "sku_eval", res)
    return res


def market_price_curve(pr: "SkuPricer", ns=(1, 3, 5, 10, 20, 40), min_ref: int = 5, reps: int = 20,
                       seed: int = 0) -> dict:
    """A TERMÉK PIACI ÁRÁNAK becslési hibája az azonos termék eladásszámának függvényében.

    Azonos cikkszámú eladások véletlen, diszjunkt felosztása: n eladásból becslünk (kép+szöveg
    előzetes nélkül, tehát konzervatívan), a referencia („valódi piaci ár”) a többi ≥ min_ref
    eladás mediánja. A referencia saját zaja miatt a mért hiba felső becslés."""
    rng = np.random.default_rng(seed)
    d = pr.df[pr.df.pattern_code.notna()].drop_duplicates("group")
    out = {}
    for m, g in d.groupby("market"):
        rows = {}
        for key, gg in g.groupby("sku_key"):
            y = gg.y_log.values - np.array([pr.cond_adj(m, c) for c in gg.condition])
            for n in ns:
                if len(y) < n + min_ref:
                    continue
                for _ in range(reps):
                    perm = rng.permutation(len(y))
                    est, ref = np.mean(y[perm[:n]]), np.median(y[perm[n:]])
                    rows.setdefault(n, []).append(abs(math.exp(est - ref) - 1))
        out[m] = {str(n): {"skus": None, "samples": len(v), "mdape": float(np.median(v)),
                           "within_10pct": float(np.mean(np.array(v) <= 0.10))}
                  for n, v in sorted(rows.items())}
    return out


def noise_floor(conn=None) -> dict:
    """A piac saját szórása: azonos cikkszám eladásai mennyire térnek el egymástól.

    Egy EGYEDI eladási árat ennél pontosabban egyetlen modell sem tud eltalálni;
    a termék TIPIKUS piaci árát viszont sok eladásból ennél pontosabban is lehet becsülni."""
    df = load_frame(conn)
    d = df[df.sku_key.notna() & df.pattern_code.notna()].drop_duplicates("group")
    out = {}
    for m, g in d.groupby("market"):
        apes = []
        for _, gg in g.groupby("sku_key"):
            if len(gg) >= 3:
                for i in range(len(gg)):
                    rest = np.delete(gg.y_log.values, i)
                    apes.append(abs(math.exp(np.median(rest)) - math.exp(gg.y_log.values[i])) / math.exp(gg.y_log.values[i]))
        out[m] = {"skus_with_3plus": int(sum(len(gg) >= 3 for _, gg in g.groupby("sku_key"))),
                  "n": len(apes), "loo_mdape": float(np.median(apes)) if apes else None,
                  "within_10pct": float(np.mean(np.array(apes) <= 0.10)) if apes else None}
    return out


def settings_target() -> float:
    return float(settings.get("validation.max_mdape", 0.10))


def sales_needed(sigma: float, target_mdape: float = 0.10, target_share: float = 0.90, tol: float = 0.10) -> dict:
    """Hány eladás kell ugyanabból a termékből a célpontossághoz (normál log-hibával, σ/√n)?

    - a piaci ár becslésének mediánhibája ≤ cél,
    - P(|hiba| ≤ tol) ≥ arány (pontos numerikus keresés).
    Egy egyedi eladás árát a piaci szórás miatt ennél pontosabban nem lehet eltalálni."""
    n_md = 1
    while math.exp(0.6745 * sigma / math.sqrt(n_md)) - 1 > target_mdape and n_md < 100000:
        n_md += 1
    n_share = 1
    while prob_within(sigma / math.sqrt(n_share), tol) < target_share and n_share < 100000:
        n_share += 1
    return {"sigma": sigma, "n_for_mdape": n_md, "n_for_share": n_share,
            "single_sale_mdape_floor": math.exp(0.6745 * sigma) - 1}
