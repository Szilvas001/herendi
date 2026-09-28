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
    """Hasonló ár-rekordok visszakeresése piac × márka partíciókban.

    A vektor a normalizált blokkok (CLIP kanonikus leírás, CLIP cím, TF-IDF és –
    ha van – CLIP kép) összefűzése, egészében normalizálva; a belső szorzat így
    a blokk-koszinuszok súlyozott átlaga. Nagy partíciónál FAISS IVF-index
    (közelítő), kisebbnél pontos keresés – százezres indexszel is gyors."""

    BLOCKS = ("clip_canon", "clip_title", "tfidf")
    EXACT_BELOW = 60_000

    def __init__(self, blocks: dict, meta: pd.DataFrame):
        self.meta = meta.reset_index(drop=True)
        self.vec = self.combine(blocks)
        brands = [b if isinstance(b, str) else "" for b in self.meta.brand]
        self.parts: dict = {}
        for key in set(zip(self.meta.market, brands)):
            idx = np.array([i for i, kk in enumerate(zip(self.meta.market, brands)) if kk == key])
            self.parts[key] = (idx, self._index(self.vec[idx]))
        self.groups = self.meta.group.astype(str).values if "group" in self.meta else None

    @classmethod
    def combine(cls, blocks: dict) -> np.ndarray:
        parts = [_nz(blocks[k].astype(np.float32)) for k in cls.BLOCKS if k in blocks]
        if "clip_image" in blocks and "image_mask" in blocks:
            parts.append(_nz(blocks["clip_image"].astype(np.float32)) * blocks["image_mask"])
        return np.ascontiguousarray(_nz(np.concatenate(parts, axis=1)).astype(np.float32))

    def _index(self, x: np.ndarray):
        try:
            import faiss
        except ImportError:
            return ("numpy", x)
        d = x.shape[1]
        if len(x) < self.EXACT_BELOW:
            ix = faiss.IndexFlatIP(d)
        else:
            nlist = int(4 * math.sqrt(len(x)))
            ix = faiss.IndexIVFFlat(faiss.IndexFlatIP(d), d, nlist, faiss.METRIC_INNER_PRODUCT)
            ix.train(x[np.random.default_rng(0).choice(len(x), min(len(x), 50 * nlist), replace=False)])
            ix.nprobe = 16
        ix.add(x)
        return ("faiss", ix)

    @staticmethod
    def _search(index, q: np.ndarray, k: int):
        kind, ix = index
        if kind == "faiss":
            return ix.search(q, k)
        sims, ids = [], []
        for i in range(0, len(q), 256):
            s_ = q[i:i + 256] @ ix.T
            kk = min(k, s_.shape[1])
            top = np.argpartition(-s_, kk - 1, axis=1)[:, :kk]
            ts = np.take_along_axis(s_, top, 1)
            order = np.argsort(-ts, axis=1)
            ids.append(np.take_along_axis(top, order, 1))
            sims.append(np.take_along_axis(ts, order, 1))
        return np.concatenate(sims), np.concatenate(ids)

    def neighbors(self, blocks: dict, q_meta: pd.DataFrame, k: int = 10, exclude_same_group: bool = True,
                  same_market: str | None = None) -> list[list[tuple[int, float]]]:
        qv = self.combine(blocks)
        q_meta = q_meta.reset_index(drop=True)
        out: list = [[] for _ in range(len(q_meta))]
        brands = [b if isinstance(b, str) else "" for b in q_meta.brand]
        markets = [same_market or m for m in q_meta.market]
        qgroups = [None if g is None or (isinstance(g, float) and g != g) else str(g)
                   for g in (q_meta.group if "group" in q_meta else [None] * len(q_meta))]
        by_part: dict = {}
        for i, key in enumerate(zip(markets, brands)):
            by_part.setdefault(key, []).append(i)
        for key, rows in by_part.items():
            if key not in self.parts:
                continue
            idx, index = self.parts[key]
            kk = min(len(idx), k + (20 if exclude_same_group else 0))
            if kk == 0:
                continue
            sims, ids = self._search(index, qv[rows], kk)
            for r, srow, irow in zip(rows, sims, ids):
                res = []
                for sim, j in zip(srow, irow):
                    if j < 0:
                        continue
                    gj = int(idx[j])
                    if exclude_same_group and self.groups is not None and qgroups[r] is not None \
                            and self.groups[gj] == qgroups[r]:
                        continue
                    res.append((gj, float(sim)))
                    if len(res) >= k:
                        break
                out[r] = res
        return out

    def knn_features(self, blocks, q_meta, y_log: np.ndarray, market: str, k: int = 10,
                     exclude_same_group: bool = True) -> np.ndarray:
        """[súlyozott log-ár (standardizálandó), max hasonlóság, átlag top5 hasonlóság, log szomszédszám]."""
        nbrs = self.neighbors(blocks, q_meta, k, exclude_same_group, same_market=market)
        feats = []
        mm = self.meta.market.values == market
        fallback = float(np.median(y_log[mm])) if mm.any() else 0.0
        for lst in nbrs:
            if not lst:
                feats.append([fallback, 0.0, 0.0, 0.0])
                continue
            s_ = np.array([x[1] for x in lst])
            w = np.exp((s_ - s_.max()) * 20)
            ys = np.array([y_log[j] for j, _ in lst])
            feats.append([float((w * ys).sum() / w.sum()), float(s_.max()), float(s_[:5].mean()),
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

    def fit(self, X, y, market_idx, Xv, yv, mv, seed: int = 0, log=print, init: "DeepModel | None" = None,
            lr: float = 1e-3, zero_cols: tuple[int, int] | None = None):
        """Tanítás korai megállással a validációs pinball-veszteségen.

        `init`: előtanított modell (finomhangolás: a súlyok onnan indulnak, a célváltozó
        középértéke is onnan jön). `zero_cols`: ablation – ezek az oszlopok végig nullák.
        Nagy adatnál (> 20 000 sor) nagyobb batch és rövidebb türelem; GPU, ha elérhető."""
        torch = _torch()
        torch.use_deterministic_algorithms(True, warn_only=True)
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.d_in = X.shape[1]
        self.zero_cols = zero_cols
        if init is not None:
            self.y_mean = init.y_mean.copy()
        else:
            self.y_mean = np.array([y[market_idx == i].mean() if (market_idx == i).any() else 0.0
                                    for i in range(len(MARKETS))], np.float32)
        big = len(X) > 20_000
        batch = 1024 if big else 128
        epochs = min(self.epochs, 60) if big else self.epochs
        patience_max = 6 if big else 40
        q = torch.tensor(QUANTILES, device=dev)

        def loss_fn(pred, yt, mi):
            sel = pred[torch.arange(len(mi), device=dev), mi]           # (N, 3)
            diff = yt[:, None] - sel
            return torch.maximum(q * diff, (q - 1) * diff).mean()

        def prep(A):
            A = A.copy() if zero_cols else A
            if zero_cols:
                A[:, zero_cols[0]:zero_cols[1]] = 0.0
            return torch.tensor(A)

        Xt, yt, mt = prep(X), torch.tensor(y - self.y_mean[market_idx], dtype=torch.float32), torch.tensor(market_idx)
        Xvt = prep(Xv).to(dev)
        yvt = torch.tensor(yv - self.y_mean[mv], dtype=torch.float32, device=dev)
        mvt = torch.tensor(mv, device=dev)
        self.states, self.best_epochs = [], []
        for s in range(self.n_seeds):
            torch.manual_seed(seed * 100 + s)
            gen = torch.Generator().manual_seed(seed * 100 + s)
            net = build_net(self.d_in)
            if init is not None:
                net.load_state_dict(init.states[s % len(init.states)])
            net.to(dev)
            opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-2)
            best, best_state, best_ep, patience = float("inf"), None, 0, 0
            for ep in range(epochs):
                net.train()
                perm = torch.randperm(len(Xt), generator=gen)
                for i in range(0, len(perm), batch):
                    b = perm[i:i + batch]
                    xb = Xt[b].clone()
                    if self.image_slice and not zero_cols:
                        drop = torch.rand(len(b), generator=gen) < 0.3
                        a, e = self.image_slice
                        xb[drop, a:e] = 0.0
                    opt.zero_grad()
                    loss = loss_fn(net(xb.to(dev)), yt[b].to(dev), mt[b].to(dev))
                    loss.backward()
                    opt.step()
                net.eval()
                with torch.no_grad():
                    vl = float(np.mean([float(loss_fn(net(Xvt[i:i + 8192]), yvt[i:i + 8192], mvt[i:i + 8192]))
                                        for i in range(0, len(Xvt), 8192)])) if len(Xvt) else 0.0
                if vl < best - 1e-4:
                    best, best_state, best_ep, patience = vl, {k: v.detach().cpu().clone()
                                                               for k, v in net.state_dict().items()}, ep, 0
                else:
                    patience += 1
                    if patience >= patience_max:
                        break
            self.states.append(best_state)
            self.best_epochs.append(best_ep)
            log(f"    seed {s}: legjobb epoch {best_ep}, val pinball {best:.4f}")
        return self

    def predict(self, X: np.ndarray, market: str) -> np.ndarray:
        torch = _torch()
        mi = MARKETS.index(market)
        if getattr(self, "zero_cols", None):
            X = X.copy()
            X[:, self.zero_cols[0]:self.zero_cols[1]] = 0.0
        preds = []
        with torch.no_grad():
            for st in self.states:
                net = build_net(self.d_in)
                net.load_state_dict(st)
                net.eval()
                preds.append(np.concatenate([net(torch.tensor(X[i:i + 16384]))[:, mi, :].numpy()
                                             for i in range(0, len(X), 16384)]) if len(X) else np.zeros((0, 3)))
        p = np.mean(preds, axis=0) + self.y_mean[mi]
        p.sort(axis=1)
        return p

    def save(self, path):
        torch = _torch()
        torch.save({"states": self.states, "d_in": self.d_in, "y_mean": self.y_mean,
                    "image_slice": self.image_slice, "best_epochs": self.best_epochs,
                    "zero_cols": getattr(self, "zero_cols", None)}, path)

    @classmethod
    def load(cls, path):
        torch = _torch()
        blob = torch.load(path, map_location="cpu", weights_only=False)
        m = cls(n_seeds=len(blob["states"]), image_slice=blob["image_slice"])
        m.states, m.d_in, m.y_mean = blob["states"], blob["d_in"], blob["y_mean"]
        m.best_epochs = blob.get("best_epochs")
        m.zero_cols = blob.get("zero_cols")
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
