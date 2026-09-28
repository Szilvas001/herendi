"""Árbecslő modellek.

1. `GroupMedianBaseline` – egyszerű alapmodell: piac × márka × tárgytípus medián
   (hierarchikus visszaeséssel), intervallum a csoport reziduumaiból.
2. `GBMModel` – klasszikus összehasonlító: gradient boosting kvantilis-regresszió
   strukturált + TF-IDF jellemzőkön.
3. `DeepModel` – multimodális neurális becslő: fagyasztott CLIP kép- és
   szövegbeágyazás + strukturált + TF-IDF + visszakeresett hasonló tételek
   jellemzői → közös törzs, piaconkénti (HU/US) kvantilisfejek (q10/q50/q90),
   5 tagú seed-ensemble, kép-modalitás dropout.
Mindhárom piac saját pénznemében, log-skálán becsül.

Közös utólagos lépések: konformális (CQR) intervallum-kalibráció a validációs
halmazon és validációs találati arányra épülő megbízhatóság.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

QUANTILES = (0.1, 0.5, 0.9)
MARKETS = ("HU", "US")
HIT_TOL = 0.25            # "találat": |becslés/tény - 1| <= 25%


# ---------------------------------------------------------------------------
# Retrieval: hasonló, korábbi ár-rekordok
# ---------------------------------------------------------------------------
def _nz(x):
    return x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-8, None)


class Retrieval:
    """Koszinusz-hasonlóság több blokk átlagaként; kép csak ha mindkét oldalon van."""

    BLOCKS = ("clip_canon", "clip_title", "tfidf")

    def __init__(self, blocks: dict, meta: pd.DataFrame):
        self.vecs = {k: _nz(blocks[k]) for k in self.BLOCKS if k in blocks}
        self.img = _nz(blocks["clip_image"]) if "clip_image" in blocks else None
        self.mask = blocks["image_mask"][:, 0] if "image_mask" in blocks else None
        self.meta = meta.reset_index(drop=True)

    def similarity(self, blocks: dict) -> np.ndarray:
        sims = [(_nz(blocks[k]) @ self.vecs[k].T) for k in self.vecs]
        s = np.sum(sims, axis=0)
        cnt = float(len(sims))
        if self.img is not None and "clip_image" in blocks:
            both = blocks["image_mask"][:, 0][:, None] * self.mask[None, :]
            s = s + both * (_nz(blocks["clip_image"]) @ self.img.T)
            return s / (cnt + both)
        return s / cnt

    def neighbors(self, blocks: dict, q_meta: pd.DataFrame, k: int = 10, exclude_same_group: bool = True,
                  same_market: str | None = None) -> list[list[tuple[int, float]]]:
        sim = self.similarity(blocks)
        out = []
        m_brand = self.meta.brand.values
        m_market = self.meta.market.values
        m_group = self.meta.group.values if "group" in self.meta else None
        for i in range(sim.shape[0]):
            row = sim[i].copy()
            q = q_meta.iloc[i]
            row[m_brand != q.get("brand")] = -np.inf
            if same_market:
                row[m_market != same_market] = -np.inf
            if exclude_same_group and m_group is not None and q.get("group") is not None:
                row[m_group == q.get("group")] = -np.inf
            idx = np.argpartition(-row, min(k, len(row) - 1))[:k]
            idx = idx[np.argsort(-row[idx])]
            out.append([(int(j), float(row[j])) for j in idx if np.isfinite(row[j])])
        return out

    def knn_features(self, blocks, q_meta, y_log: np.ndarray, market: str, k: int = 10,
                     exclude_same_group: bool = True) -> np.ndarray:
        """[súlyozott log-ár (standardizálandó), max hasonlóság, átlag top5 hasonlóság, log szomszédszám]."""
        nbrs = self.neighbors(blocks, q_meta, k, exclude_same_group, same_market=market)
        feats = []
        fallback = float(np.median(y_log[self.meta.market.values == market])) if (self.meta.market == market).any() else 0.0
        for lst in nbrs:
            if not lst:
                feats.append([fallback, 0.0, 0.0, 0.0])
                continue
            s = np.array([x[1] for x in lst])
            w = np.exp((s - s.max()) * 20)
            ys = np.array([y_log[j] for j, _ in lst])
            feats.append([float((w * ys).sum() / w.sum()), float(s.max()), float(s[:5].mean()),
                          math.log1p(len(lst))])
        return np.asarray(feats, np.float32)


# ---------------------------------------------------------------------------
# 1. Baseline
# ---------------------------------------------------------------------------
class GroupMedianBaseline:
    name = "baseline_group_median"

    def fit(self, df: pd.DataFrame):
        self.tables = {}
        for keys in (("market", "brand", "object_type"), ("market", "brand"), ("market",)):
            g = df.groupby(list(keys)).y_log
            self.tables[keys] = {k if isinstance(k, tuple) else (k,): (v.median(), v.quantile(0.1) - v.median(),
                                                                      v.quantile(0.9) - v.median(), len(v))
                                 for k, v in g}
        return self

    def predict(self, df: pd.DataFrame, market: str) -> np.ndarray:
        out = []
        for _, r in df.iterrows():
            for keys in self.tables:
                key = tuple(market if k == "market" else r.get(k) for k in keys)
                hit = self.tables[keys].get(key)
                if hit and hit[3] >= 5:
                    med, lo, hi, _ = hit
                    out.append([med + lo, med, med + hi])
                    break
            else:
                out.append([np.nan] * 3)
        return np.asarray(out, np.float64).reshape(-1, 3)

    def state(self):
        return {"|".join(k): {"|".join(map(str, kk)): v for kk, v in t.items()} for k, t in self.tables.items()}

    @classmethod
    def from_state(cls, st):
        m = cls()
        m.tables = {tuple(k.split("|")): {tuple(kk.split("|")): tuple(v) for kk, v in t.items()} for k, t in st.items()}
        return m


# ---------------------------------------------------------------------------
# 2. Gradient boosting (klasszikus összehasonlító)
# ---------------------------------------------------------------------------
class GBMModel:
    name = "gbm_quantile"

    def fit(self, X: np.ndarray, y: np.ndarray, seed: int = 0):
        from sklearn.ensemble import HistGradientBoostingRegressor
        self.models = [HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=300, learning_rate=0.05,
                                                     max_leaf_nodes=15, min_samples_leaf=10, l2_regularization=1.0,
                                                     random_state=seed).fit(X, y) for q in QUANTILES]
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        p = np.stack([m.predict(X) for m in self.models], axis=1)
        p.sort(axis=1)
        return p


# ---------------------------------------------------------------------------
# 3. Deep multimodális modell
# ---------------------------------------------------------------------------
def _torch():
    import torch
    return torch


def build_net(d_in: int, hidden: int = 256, p: float = 0.25):
    torch = _torch()
    nn = torch.nn

    class QuantileNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.trunk = nn.Sequential(nn.Linear(d_in, hidden), nn.GELU(), nn.Dropout(p),
                                       nn.Linear(hidden, hidden // 2), nn.GELU(), nn.Dropout(p))
            self.heads = nn.ModuleList([nn.Linear(hidden // 2, 3) for _ in MARKETS])

        def forward(self, x):
            h = self.trunk(x)
            outs = []
            for head in self.heads:
                o = head(h)
                mid = o[:, 1]
                lo = mid - nn.functional.softplus(o[:, 0])
                hi = mid + nn.functional.softplus(o[:, 2])
                outs.append(torch.stack([lo, mid, hi], dim=1))
            return torch.stack(outs, dim=1)   # (N, markets, 3)

    return QuantileNet()


class DeepModel:
    name = "deep_multimodal"

    def __init__(self, n_seeds: int = 5, image_slice: tuple[int, int] | None = None, epochs: int = 400):
        self.n_seeds = n_seeds
        self.image_slice = image_slice      # (start, end) oszlopok: kép + maszk → modalitás-dropout
        self.epochs = epochs
        self.states = []

    def fit(self, X, y, market_idx, Xv, yv, mv, seed: int = 0, log=print):
        torch = _torch()
        torch.use_deterministic_algorithms(True, warn_only=True)
        self.d_in = X.shape[1]
        self.y_mean = np.array([y[market_idx == i].mean() if (market_idx == i).any() else 0.0
                                for i in range(len(MARKETS))], np.float32)
        q = torch.tensor(QUANTILES)

        def loss_fn(pred, yt, mi):
            sel = pred[torch.arange(len(mi)), mi]           # (N, 3)
            diff = yt[:, None] - sel
            return torch.maximum(q * diff, (q - 1) * diff).mean()

        Xt, yt, mt = (torch.tensor(X), torch.tensor(y - self.y_mean[market_idx], dtype=torch.float32),
                      torch.tensor(market_idx))
        Xvt, yvt, mvt = (torch.tensor(Xv), torch.tensor(yv - self.y_mean[mv], dtype=torch.float32),
                         torch.tensor(mv))
        self.states, self.best_epochs = [], []
        for s in range(self.n_seeds):
            torch.manual_seed(seed * 100 + s)
            gen = torch.Generator().manual_seed(seed * 100 + s)
            net = build_net(self.d_in)
            opt = torch.optim.AdamW(net.parameters(), lr=1e-3, weight_decay=1e-2)
            best, best_state, best_ep, patience = float("inf"), None, 0, 0
            for ep in range(self.epochs):
                net.train()
                perm = torch.randperm(len(Xt), generator=gen)
                for i in range(0, len(perm), 128):
                    b = perm[i:i + 128]
                    xb = Xt[b].clone()
                    if self.image_slice:
                        drop = torch.rand(len(b), generator=gen) < 0.3
                        a, e = self.image_slice
                        xb[drop, a:e] = 0.0
                    opt.zero_grad()
                    loss = loss_fn(net(xb), yt[b], mt[b])
                    loss.backward()
                    opt.step()
                net.eval()
                with torch.no_grad():
                    vl = float(loss_fn(net(Xvt), yvt, mvt))
                if vl < best - 1e-4:
                    best, best_state, best_ep, patience = vl, {k: v.clone() for k, v in net.state_dict().items()}, ep, 0
                else:
                    patience += 1
                    if patience >= 40:
                        break
            self.states.append(best_state)
            self.best_epochs.append(best_ep)
            log(f"    seed {s}: legjobb epoch {best_ep}, val pinball {best:.4f}")
        return self

    def predict(self, X: np.ndarray, market: str) -> np.ndarray:
        torch = _torch()
        mi = MARKETS.index(market)
        preds = []
        with torch.no_grad():
            for st in self.states:
                net = build_net(self.d_in)
                net.load_state_dict(st)
                net.eval()
                preds.append(net(torch.tensor(X))[:, mi, :].numpy())
        p = np.mean(preds, axis=0) + self.y_mean[mi]
        p.sort(axis=1)
        return p

    def save(self, path):
        torch = _torch()
        torch.save({"states": self.states, "d_in": self.d_in, "y_mean": self.y_mean,
                    "image_slice": self.image_slice, "best_epochs": self.best_epochs}, path)

    @classmethod
    def load(cls, path):
        torch = _torch()
        blob = torch.load(path, map_location="cpu", weights_only=False)
        m = cls(n_seeds=len(blob["states"]), image_slice=blob["image_slice"])
        m.states, m.d_in, m.y_mean = blob["states"], blob["d_in"], blob["y_mean"]
        m.best_epochs = blob.get("best_epochs")
        return m


# ---------------------------------------------------------------------------
# Kalibráció és megbízhatóság
# ---------------------------------------------------------------------------
def conformal_offset(pred: np.ndarray, y: np.ndarray, alpha: float = 0.2) -> float:
    """CQR: az a log-eltolás, amellyel a [q10, q90] a validáción ~80%-ot fed le."""
    if len(y) < 10:
        return 0.0
    scores = np.maximum(pred[:, 0] - y, y - pred[:, 2])
    k = min(len(y) - 1, int(math.ceil((1 - alpha) * (len(y) + 1))) - 1)
    return float(np.sort(scores)[k])


def apply_offset(pred: np.ndarray, off: float) -> np.ndarray:
    p = pred.copy()
    p[:, 0] -= off
    p[:, 2] += off
    return p


def confidence_table(pred: np.ndarray, y: np.ndarray, bins: int = 4) -> dict:
    """Intervallum-szélesség szerinti sávok → validációs találati arány (±25%)."""
    width = pred[:, 2] - pred[:, 0]
    hit = np.abs(np.exp(pred[:, 1] - y) - 1) <= HIT_TOL
    if len(y) < 20:
        return {"edges": [], "rates": [float((hit.sum() + 1) / (len(hit) + 2))] if len(hit) else [0.0], "n": len(y)}
    edges = list(np.quantile(width, np.linspace(0, 1, bins + 1))[1:-1])
    idx = np.digitize(width, edges)
    rates = [float((hit[idx == b].sum() + 1) / ((idx == b).sum() + 2)) for b in range(bins)]
    # monoton: szélesebb intervallum nem lehet megbízhatóbb
    for b in range(1, len(rates)):
        rates[b] = min(rates[b], rates[b - 1])
    return {"edges": [float(e) for e in edges], "rates": rates, "n": int(len(y))}


def confidence_of(pred: np.ndarray, table: dict) -> np.ndarray:
    width = pred[:, 2] - pred[:, 0]
    if not table["edges"]:
        return np.full(len(pred), table["rates"][0])
    return np.asarray(table["rates"])[np.digitize(width, table["edges"])]


# ---------------------------------------------------------------------------
# Metrikák
# ---------------------------------------------------------------------------
def bootstrap_ci(est: np.ndarray, actual: np.ndarray, n: int = 1000, seed: int = 0) -> dict:
    """95%-os bootstrap intervallum az MdAPE-re és a MAE-re (tesztminták újramintavételezése)."""
    rng = np.random.default_rng(seed)
    ape = np.abs(est - actual) / actual
    ae = np.abs(est - actual)
    idx = rng.integers(0, len(ape), size=(n, len(ape)))
    md = np.median(ape[idx], axis=1)
    mae = ae[idx].mean(axis=1)
    return {"mdape_ci95": [float(np.quantile(md, 0.025)), float(np.quantile(md, 0.975))],
            "mae_ci95": [float(np.quantile(mae, 0.025)), float(np.quantile(mae, 0.975))]}


def metrics(pred: np.ndarray, y_log: np.ndarray) -> dict:
    ok = ~np.isnan(pred[:, 1])
    if ok.sum() == 0:
        return {"n": 0}
    p, y = pred[ok], y_log[ok]
    est, actual = np.exp(p[:, 1]), np.exp(y)
    ape = np.abs(est - actual) / actual
    return {
        "n": int(ok.sum()),
        "coverage_pct": round(100 * ok.mean(), 1),
        "mae": float(np.mean(np.abs(est - actual))),
        "median_ae": float(np.median(np.abs(est - actual))),
        "mdape": float(np.median(ape)),
        "mape": float(np.mean(ape)),
        "within_25pct": float(np.mean(ape <= HIT_TOL)),
        "interval80_coverage": float(np.mean((y >= p[:, 0]) & (y <= p[:, 2]))),
        "interval_median_rel_width": float(np.median(np.exp(p[:, 2]) / np.exp(p[:, 1]) - np.exp(p[:, 0]) / np.exp(p[:, 1]))),
        **(bootstrap_ci(est, actual) if len(est) >= 5 else {}),
        "pinball": float(np.mean([np.mean(np.maximum(q * (y - p[:, i]), (q - 1) * (y - p[:, i])))
                                  for i, q in enumerate(QUANTILES)])),
    }
