"""Betanított modellverzió betöltése és becslés hirdetésekre (újratanítás nélkül).

A dashboard indulásakor / a pontozó feladatban töltődik be a `models/CURRENT`
szerinti verzió. Minden becslés tartalmazza a modellverziót, a kiválasztott
modellt, a célváltozó alapját és a felhasznált összehasonlító rekordokat.
"""
from __future__ import annotations

import json
import logging
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from . import dataset, settings, text, vision
from .model import (MARKETS, DeepModel, GroupMedianBaseline, Retrieval, apply_offset, confidence_of)
from .train import design, knn_block

log = logging.getLogger(__name__)


class ModelMissing(RuntimeError):
    pass


def current_version(models_dir: Path | None = None) -> str | None:
    d = Path(models_dir or settings.path("models_dir"))
    f = d / "CURRENT"
    if f.exists():
        v = f.read_text().strip()
        if (d / v / "manifest.json").exists():
            return v
    return None


def load_manifest(version: str | None = None, models_dir: Path | None = None) -> dict | None:
    d = Path(models_dir or settings.path("models_dir"))
    version = version or current_version(d)
    if not version:
        return None
    return json.loads((d / version / "manifest.json").read_text())


class Estimator:
    def __init__(self, version: str | None = None, models_dir: Path | None = None):
        d = Path(models_dir or settings.path("models_dir"))
        self.version = version or current_version(d)
        if not self.version:
            raise ModelMissing("Nincs betanított modell (models/CURRENT). Futtasd: python -m porcelan train")
        self.dir = d / self.version
        self.manifest = json.loads((self.dir / "manifest.json").read_text())
        with (self.dir / "pipeline.pkl").open("rb") as fh:
            self.pipe = pickle.load(fh)
        self.base = GroupMedianBaseline.from_state(json.loads((self.dir / "baseline.json").read_text()))
        with (self.dir / "gbm.pkl").open("rb") as fh:
            self.gbms = pickle.load(fh)
        self.deep = DeepModel.load(self.dir / "deep.pt")
        self.deep_nc = DeepModel.load(self.dir / "deep_no_clip.pt") if (self.dir / "deep_no_clip.pt").exists() else None
        self.extra_deep = {n: DeepModel.load(self.dir / f"{n}.pt") for n in ("deep_pretrained_ft", "deep_no_image")
                           if (self.dir / f"{n}.pt").exists()}
        idx = np.load(self.dir / "index.npz")
        self.records = pd.read_csv(self.dir / "training_data.csv.gz")
        self.records["group"] = self.records["group"].astype(str)
        split = idx["split"]
        self.y = idx["y"].astype(np.float32)
        blocks = {k: idx[k].astype(np.float32) for k in idx.files if k not in ("y", "split", "knn")}
        self.use_clip = self.manifest["use_clip"]
        tr = split == "train"
        self.train_mask = tr
        self.retr_train = Retrieval({k: v[tr] for k, v in blocks.items()}, self.records[tr])
        self.retr_all = Retrieval(blocks, self.records)
        self.y_mean = self.manifest["y_mean"]
        self.calib = self.manifest["metrics"]["calibration"]
        self.chosen = self.manifest["chosen_model"]
        self._by_ref = {str(r): g for r, g in zip(self.records.source_ref.astype(str), self.records.group)}

    def _beats_baseline(self, market: str) -> bool:
        """A választott modell a TESZTEN jobb-e a csoportmedián-alapmodellnél (MdAPE)."""
        test = self.manifest["metrics"]["test"]
        name = self.chosen.get(market)
        m, b = test.get(f"{name}/{market}", {}), test.get(f"baseline_group_median/{market}", {})
        if name == "baseline_group_median" or m.get("mdape") is None or b.get("mdape") is None:
            return False
        return m["mdape"] < b["mdape"]

    # ------------------------------------------------------------------
    def _frame(self, listings: list[dict]) -> pd.DataFrame:
        rows = []
        for l in listings:
            f = text.extract(l.get("title") or "", l.get("description") or "", l.get("category") or "")
            rows.append({
                "listing_id": l.get("id"), "source_ref": str(l.get("source_id")), "title": l.get("title") or "",
                "description": l.get("description") or "", "brand": f["brand"], "object_type": f["object_type"],
                "decor": f["decor"], "size_cm": f["size_cm"], "pieces": f["pieces"], "condition": f["condition"],
                "damage_flags": f["damage_flags"], "mark_flags": f["mark_flags"], "suspect_flags": f["suspect_flags"],
                "canonical_en": f["canonical_en"], "observed_at": pd.Timestamp.now(tz="UTC"),
                # saját (vagy újrahirdetett) rekord kizárása a szomszédok közül
                "group": self._by_ref.get(str(l.get("source_id"))),
            })
        return pd.DataFrame(rows)

    def predict(self, listings: list[dict], conn=None) -> list[dict]:
        if not listings:
            return []
        df = self._frame(listings)
        blocks = self.pipe.transform(df, conn)
        out = [{"model_version": self.version, "markets": {}} for _ in listings]
        for market in MARKETS:
            name = self.chosen.get(market)
            if not name:
                continue
            meta = df.assign(market=market)
            knn = knn_block(self.retr_train, blocks, meta, self.y[self.train_mask], self.y_mean)
            if name == "baseline_group_median":
                pred = self.base.predict(meta, market)
            elif name == "gbm_quantile":
                Xg = np.concatenate([blocks["struct"], blocks["tfidf"], knn], axis=1)
                pred = self.gbms[market].predict(Xg)
            elif name == "deep_no_clip":
                Xn = np.concatenate([blocks["struct"], blocks["tfidf"], knn], axis=1).astype(np.float32)
                pred = self.deep_nc.predict(Xn, market)
            else:
                X, _ = design(blocks, knn, self.use_clip)
                pred = self.extra_deep.get(name, self.deep).predict(X, market)
            cal = self.calib.get(f"{name}/{market}", {})
            pred = apply_offset(pred, cal.get("conformal_offset", 0.0))
            conf = confidence_of(pred, cal["confidence"]) if cal.get("confidence") else np.zeros(len(pred))
            nbrs = self.retr_all.neighbors(blocks, meta, k=5, exclude_same_group=True, same_market=market)
            currency = dataset.CURRENCY[market]
            for i in range(len(df)):
                if np.isnan(pred[i, 1]):
                    continue
                q = np.exp(pred[i])
                comps = []
                for j, sim in nbrs[i]:
                    r = self.records.iloc[j]
                    comps.append({"title": r.title, "price": float(r.y_native), "currency": currency,
                                  "price_type": r.price_type, "observed_at": str(r.observed_at)[:10],
                                  "source": r.source, "url": r.url if isinstance(r.url, str) else None,
                                  "similarity": round(sim, 3)})
                out[i]["markets"][market] = {
                    "beats_baseline": self._beats_baseline(market),
                    "q10": float(q[0]), "q50": float(q[1]), "q90": float(q[2]), "currency": currency,
                    "confidence": float(conf[i]), "model": name,
                    "basis": self.manifest["target_basis"].get(market),
                    "top_similarity": comps[0]["similarity"] if comps else 0.0,
                    "comparables": comps,
                }
        for i, row in df.iterrows():
            out[i]["features"] = {k: (None if (isinstance(v, float) and np.isnan(v)) else v)
                                  for k, v in row[["brand", "object_type", "decor", "size_cm", "pieces", "condition",
                                                   "damage_flags", "mark_flags", "suspect_flags",
                                                   "canonical_en"]].items()}
            out[i]["image_used"] = bool(blocks.get("image_mask", np.zeros((len(df), 1)))[i, 0]) if self.use_clip else False
        self._apply_sku(listings, out, conn)
        return out


    # ------------------------------------------------------------------
    def _sku_pricer(self, conn):
        if getattr(self, "_sku", None) is None:
            from . import sku_model
            try:
                self._sku = sku_model.SkuPricer(sku_model.load_frame(conn))
            except Exception as exc:  # pragma: no cover - adatbázis nélküli környezet
                log.warning("Cikkszám-modell nem tölthető: %s", exc)
                self._sku = False
        return self._sku or None

    def _apply_sku(self, listings: list[dict], out: list[dict], conn) -> None:
        """Pontosan azonosított terméknél: azonos cikkszám / formaszám eladásai + a kép+szöveg modell
        (előzetes becslés) bizonytalansággal súlyozott kombinációja; P(|hiba| ≤ 10%)."""
        from . import db as _db
        from .identify import identify_text
        from .sku_model import Z80, prob_within
        pricer = self._sku_pricer(conn or _db.get_conn())
        sku_eval = _db.get_meta(conn or _db.get_conn(), "sku_eval") or {}
        for i, l in enumerate(listings):
            key = l.get("sku_key")
            basis = l.get("id_basis")
            if not key:
                ident = identify_text(l.get("title") or "", l.get("description") or "")
                key, basis = ident.sku_key, '["szöveg"]'
            if not key:
                continue
            brand, form, pat = key.split("|")
            out[i]["identity"] = {"sku_key": key, "brand": brand, "form_no": form,
                                  "pattern_code": None if pat == "-" else pat,
                                  "confidence": l.get("id_confidence"), "basis": basis}
            if not pricer:
                continue
            for market, m in out[i]["markets"].items():
                mu0 = float(np.log(m["q50"]))
                sd0 = max(1e-3, float((np.log(m["q90"]) - np.log(m["q10"])) / (2 * Z80)))
                cond = (out[i].get("features") or {}).get("condition") or l.get("condition")
                est = pricer.estimate(market, key, cond, mu0, sd0, exclude_refs={l.get("source_id")})
                if est.get("mu") is None or (est["n_exact"] == 0 and est["n_form"] == 0):
                    m["sku"] = {"n_exact": 0, "n_form": 0, "p_within_10": prob_within(sd0),
                                "note": "nincs azonos termék eladás az adatban"}
                    m["p_within_10"] = prob_within(sd0)
                    continue
                v = (sku_eval.get("by_market") or {}).get(market) or {}
                validated = (v.get("n", 0) >= 30 and (v.get("precise_within_10pct") or 0) >= 0.9)
                m["model_q"] = {k: m[k] for k in ("q10", "q50", "q90")}
                m["q10"], m["q50"], m["q90"] = (float(np.exp(est["q10"])), float(np.exp(est["mu"])),
                                                float(np.exp(est["q90"])))
                m["p_within_10"] = est["p_within_10"]
                m["sku"] = {k: est[k] for k in ("n_exact", "n_form", "p_within_10", "evidence", "sigma_market")}
                m["precise"] = bool(est["p_within_10"] >= 0.9 and validated)
                m["precise_validated"] = validated


_cache: dict = {}


def get_estimator(reload: bool = False) -> Estimator:
    v = current_version()
    if reload or _cache.get("version") != v:
        _cache["est"] = Estimator(v)
        _cache["version"] = v
    return _cache["est"]


def clip_ready() -> bool:
    return vision.available()
