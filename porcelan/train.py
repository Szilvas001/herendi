"""Reprodukálható tanítás, értékelés és verziózott mentés.

    python -m porcelan train [--seed 42] [--seeds 5] [--no-clip]

Kimenet: models/<verzió>/ (manifest.json, EVALUATION.md, súlyok, jellemző-pipeline,
visszakeresési index, tanítóadat-pillanatkép) és models/CURRENT.
"""
from __future__ import annotations

import json
import logging
import pickle
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import dataset, db, settings
from .features import FeaturePipeline, concat, structured_names
from .model import (MARKETS, DeepModel, GBMModel, GroupMedianBaseline, Retrieval, apply_offset,
                    confidence_of, confidence_table, conformal_offset, metrics)

log = logging.getLogger(__name__)
CLIP_BLOCKS = ["clip_canon", "clip_title", "clip_image", "image_mask"]


def _git_commit() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              cwd=settings.ROOT, timeout=5).stdout.strip() or None
    except Exception:
        return None


def _sub(blocks, mask):
    return {k: v[mask] for k, v in blocks.items()}


def knn_block(retr: Retrieval, blocks, meta: pd.DataFrame, y_train_log: np.ndarray, y_mean: dict,
              exclude_same_group=True) -> np.ndarray:
    out = np.zeros((len(meta), 4), np.float32)
    for market in MARKETS:
        m = (meta.market == market).values
        if not m.any():
            continue
        f = retr.knn_features(_sub(blocks, m), meta[m], y_train_log, market, exclude_same_group=exclude_same_group)
        f[:, 0] -= y_mean.get(market, 0.0)
        out[m] = f
    return out


def design(blocks, knn, use_clip: bool):
    keys = ["struct", "tfidf"] + (CLIP_BLOCKS if use_clip else [])
    X = concat(blocks, keys)
    start = sum(blocks[k].shape[1] for k in ["struct", "tfidf", "clip_canon", "clip_title"]) if use_clip else None
    image_slice = (start, start + blocks["clip_image"].shape[1] + 1) if use_clip else None
    return np.concatenate([X, knn], axis=1).astype(np.float32), image_slice


def train(conn=None, seed: int = 42, n_seeds: int = 5, use_clip: bool = True, progress=None,
          models_dir: Path | None = None) -> dict:
    t0 = time.time()
    progress = progress or (lambda f, m: log.info(m))
    conn = conn or db.get_conn()
    np.random.seed(seed)
    progress(0.02, "Tanítóadat összeállítása")
    ds = dataset.build(conn)
    df = ds.df
    if len(df) < 50:
        raise RuntimeError(f"Túl kevés tanítóadat ({len(df)} sor). Importálj vagy gyűjts adatot előbb.")
    labels, split_info = dataset.split(df, seed)
    tr, va, te = (labels == "train").values, (labels == "val").values, (labels == "test").values
    y = df.y_log.values.astype(np.float32)
    market_idx = np.array([MARKETS.index(m) for m in df.market])

    progress(0.08, "Jellemzők (TF-IDF, strukturált, CLIP) számítása")
    pipe = FeaturePipeline(use_clip=use_clip).fit(df[tr], conn)
    blocks = pipe.transform(df, conn)
    y_mean = {m: float(y[tr & (df.market == m).values].mean()) for m in MARKETS if (tr & (df.market == m).values).any()}
    retr = Retrieval(_sub(blocks, tr), df[tr])
    knn = knn_block(retr, blocks, df, y[tr], y_mean)
    X, image_slice = design(blocks, knn, use_clip)
    Xg = np.concatenate([blocks["struct"], blocks["tfidf"], knn], axis=1)

    results: dict = {"val": {}, "test": {}, "test_by_brand": {}, "calibration": {}}
    preds_val, preds_test = {}, {}

    progress(0.2, "Alapmodell (csoportmedián)")
    base = GroupMedianBaseline().fit(df[tr])
    models = {"baseline_group_median": ("baseline", base)}

    progress(0.25, "Gradient boosting összehasonlító modell")
    gbms = {}
    for m in MARKETS:
        mm = tr & (df.market == m).values
        if mm.sum() >= 30:
            gbms[m] = GBMModel().fit(Xg[mm], y[mm], seed)
    models["gbm_quantile"] = ("gbm", gbms)

    progress(0.35, "Multimodális neurális modell tanítása")
    deep = DeepModel(n_seeds=n_seeds, image_slice=image_slice).fit(
        X[tr], y[tr], market_idx[tr], X[va], y[va], market_idx[va], seed=seed, log=log.info)
    models["deep_multimodal"] = ("deep", deep)
    if use_clip:
        progress(0.6, "Ablation: neurális modell CLIP nélkül")
        Xn = np.concatenate([blocks["struct"], blocks["tfidf"], knn], axis=1).astype(np.float32)
        deep_nc = DeepModel(n_seeds=n_seeds).fit(Xn[tr], y[tr], market_idx[tr], Xn[va], y[va], market_idx[va],
                                                 seed=seed, log=log.info)
        models["deep_no_clip"] = ("deep_nc", deep_nc)

    def predict(kind, obj, mask, market):
        sub = mask & (df.market == market).values
        if not sub.any():
            return sub, np.zeros((0, 3))
        if kind == "baseline":
            return sub, obj.predict(df[sub], market)
        if kind == "gbm":
            if market not in obj:
                return sub, np.full((sub.sum(), 3), np.nan)
            return sub, obj[market].predict(Xg[sub])
        if kind == "deep_nc":
            return sub, obj.predict(Xn[sub], market)
        return sub, obj.predict(X[sub], market)

    progress(0.8, "Kalibráció és értékelés")
    for name, (kind, obj) in models.items():
        for market in MARKETS:
            vsub, pv = predict(kind, obj, va, market)
            tsub, pt = predict(kind, obj, te, market)
            if vsub.sum() == 0:
                continue
            ok = ~np.isnan(pv[:, 1])
            off = conformal_offset(pv[ok], y[vsub][ok])
            pv_c, pt_c = apply_offset(pv, off), apply_offset(pt, off)
            okc = ~np.isnan(pv_c[:, 1])
            ctab = confidence_table(pv_c[okc], y[vsub][okc])
            results["calibration"][f"{name}/{market}"] = {"conformal_offset": off, "confidence": ctab}
            results["val"][f"{name}/{market}"] = metrics(pv_c, y[vsub])
            mt = metrics(pt_c, y[tsub])
            okt = ~np.isnan(pt_c[:, 1])
            if okt.any():
                conf = confidence_of(pt_c[okt], ctab)
                hit = np.abs(np.exp(pt_c[okt, 1] - y[tsub][okt]) - 1) <= 0.25
                mt["mean_confidence"] = float(conf.mean())
                mt["realized_hit_rate"] = float(hit.mean())
            results["test"][f"{name}/{market}"] = mt
            for brand in ("Herendi", "Zsolnay"):
                bm = (df[tsub].brand == brand).values
                if bm.any():
                    results["test_by_brand"][f"{name}/{market}/{brand}"] = metrics(pt_c[bm], y[tsub][bm])
            preds_val[(name, market)] = pv_c
            preds_test[(name, market)] = pt_c

    # Modellválasztás piaconként a VALIDÁCIÓS pinball alapján (a teszt érintetlen).
    chosen = {}
    for market in MARKETS:
        cands = [(results["val"][f"{n}/{market}"].get("pinball", np.inf), n) for n in models
                 if f"{n}/{market}" in results["val"] and results["val"][f"{n}/{market}"].get("n")
                 and results["val"][f"{n}/{market}"].get("coverage_pct", 0) >= 99]
        if cands:
            chosen[market] = min(cands)[1]

    status, reasons = validation_gate(ds, results, chosen)
    version = f"v{datetime.now(timezone.utc):%Y%m%d-%H%M}-{dataset.fingerprint(df)[:8]}"
    out = Path(models_dir or settings.path("models_dir")) / version
    out.mkdir(parents=True, exist_ok=True)

    progress(0.9, "Mentés")
    with (out / "pipeline.pkl").open("wb") as fh:
        pickle.dump(pipe, fh)
    (out / "baseline.json").write_text(json.dumps(base.state(), ensure_ascii=False))
    with (out / "gbm.pkl").open("wb") as fh:
        pickle.dump(gbms, fh)
    deep.save(out / "deep.pt")
    if "deep_no_clip" in models:
        models["deep_no_clip"][1].save(out / "deep_no_clip.pt")
    np.savez_compressed(out / "index.npz", **{k: v.astype(np.float16) for k, v in blocks.items()}, knn=knn,
                        y=y, split=np.asarray(labels.tolist(), dtype="U5"))
    dataset.export(df, out / "training_data.csv.gz", labels)

    manifest = {
        "version": version,
        "created_at": db.now_iso(),
        "status": status,
        "status_reasons": reasons,
        "git_commit": _git_commit(),
        "seed": seed, "n_seeds": n_seeds, "use_clip": use_clip,
        "clip": {"model": "ViT-B-32-quickgelu", "weights": settings.get("paths.clip_weights"),
                 "sha256": settings.get("paths.clip_weights_sha256"), "frozen": True},
        "data_fingerprint": dataset.fingerprint(df),
        "dataset": ds.report,
        "target_basis": ds.basis,
        "target_currency": dataset.CURRENCY,
        "split": split_info,
        "y_mean": y_mean,
        "chosen_model": chosen,
        "image_slice": image_slice,
        "struct_features": structured_names(),
        "metrics": results,
        "deep_best_epochs": deep.best_epochs,
        "train_seconds": round(time.time() - t0, 1),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1, default=float))
    (out / "EVALUATION.md").write_text(evaluation_markdown(manifest), encoding="utf-8")
    (out.parent / "CURRENT").write_text(version + "\n")
    progress(1.0, f"Kész: {version} ({status})")
    return manifest


def validation_gate(ds, results: dict, chosen: dict) -> tuple[str, list[str]]:
    cfg = settings.get("validation")
    reasons = []
    for market in dataset.MARKETS:
        basis = ds.basis.get(market)
        name = chosen.get(market)
        if not name:
            reasons.append(f"{market}: nincs használható modell (kevés adat)")
            continue
        if basis != "realized":
            reasons.append(f"{market}: a célváltozó kínálati ár, nem realizált eladási ár")
        for brand in ("Herendi", "Zsolnay"):
            m = results["test_by_brand"].get(f"{name}/{market}/{brand}", {})
            if m.get("n", 0) < cfg["min_realized_test_samples_per_brand"]:
                reasons.append(f"{market}/{brand}: {m.get('n', 0)} tesztminta < {cfg['min_realized_test_samples_per_brand']}")
        t = results["test"].get(f"{name}/{market}", {})
        if t.get("mdape", 1) > cfg["max_mdape"]:
            reasons.append(f"{market}: MdAPE {t.get('mdape', 0):.0%} > {cfg['max_mdape']:.0%}")
        cov = t.get("interval80_coverage")
        if cov is not None and abs(cov - 0.8) > cfg["interval_coverage_tolerance"]:
            reasons.append(f"{market}: 80%-os intervallum tényleges lefedettsége {cov:.0%}")
        b = results["test"].get(f"baseline_group_median/{market}", {})
        if cfg["require_beats_baseline"] and name != "baseline_group_median" and b.get("mdape") is not None \
                and t.get("mdape", 1) >= b["mdape"]:
            reasons.append(f"{market}: a választott modell nem jobb az alapmodellnél a teszten")
    return ("validált" if not reasons else "kísérleti"), reasons


def _fmt(v, pct=False, money=False):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    if pct:
        return f"{100 * v:.1f}%"
    if money:
        return f"{v:,.0f}".replace(",", " ")
    return str(v)


def _ci(m):
    ci = m.get("mdape_ci95")
    return f"{100 * ci[0]:.0f}–{100 * ci[1]:.0f}%" if ci else "–"


def evaluation_markdown(man: dict) -> str:
    r = man["metrics"]
    lines = [f"# Modellértékelés – {man['version']}", "",
             f"**Státusz: {man['status'].upper()}**", ""]
    if man["status_reasons"]:
        lines += ["Miért nem validált:", *[f"- {x}" for x in man["status_reasons"]], ""]
    ds = man["dataset"]
    lines += ["## Adat", "",
              f"- Nyers ár-rekordok: {ds.get('raw_records')}; típus szerint: " +
              ", ".join(f"{k}: {v}" for k, v in ds.get("by_type", {}).items()),
              f"- Tanításra használt sorok (duplikátumszűrés után): {ds.get('rows')}, csoportok: {ds.get('groups')}",
              f"- Piac × márka: " + ", ".join(f"{k}: {v}" for k, v in ds.get("by_market_brand", {}).items()),
              f"- Célváltozó alapja: " + ", ".join(f"{k}: {'realizált ár' if v == 'realized' else 'KÍNÁLATI ár'}"
                                                  for k, v in man["target_basis"].items()),
              f"- Kiszűrve: {ds.get('dropped')}",
              f"- Megfigyelési napok: {', '.join(ds.get('observation_days', []))}",
              f"- Képpel rendelkező tanítósor: {ds.get('with_images', 0)}",
              f"- Felosztás: {man['split']['test']}; {man['split']['counts']}",
              f"- Adat-ujjlenyomat: `{man['data_fingerprint'][:16]}`, seed {man['seed']}, git `{(man['git_commit'] or '')[:10]}`",
              ""]
    for note in ds.get("notes", []):
        lines.append(f"> {note}")
    lines += ["", "## Tesztmetrikák (a validáción kalibrált intervallumokkal)", "",
              "| Modell | Piac | n | MAE | Medián AE | MdAPE (95% CI) | ±25%-on belül | 80%-os int. lefedettség | átl. megbízhatóság | tényleges találat |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for key, m in r["test"].items():
        name, market = key.split("/")
        cur = "Ft" if market == "HU" else "USD"
        star = " ★" if man["chosen_model"].get(market) == name else ""
        lines.append(f"| {name}{star} | {market} | {m.get('n', 0)} | {_fmt(m.get('mae'), money=True)} {cur} | "
                     f"{_fmt(m.get('median_ae'), money=True)} {cur} | {_fmt(m.get('mdape'), pct=True)} ({_ci(m)}) | "
                     f"{_fmt(m.get('within_25pct'), pct=True)} | {_fmt(m.get('interval80_coverage'), pct=True)} | "
                     f"{_fmt(m.get('mean_confidence'), pct=True)} | {_fmt(m.get('realized_hit_rate'), pct=True)} |")
    lines += ["", "★ = a validációs pinball-veszteség alapján kiválasztott, élesben használt modell.", "",
              "## Gyártónként (teszt)", "", "| Modell | Piac | Gyártó | n | MdAPE | MAE | 80%-os lefedettség |",
              "|---|---|---|---:|---:|---:|---:|"]
    for key, m in r["test_by_brand"].items():
        name, market, brand = key.split("/")
        lines.append(f"| {name} | {market} | {brand} | {m.get('n', 0)} | {_fmt(m.get('mdape'), pct=True)} | "
                     f"{_fmt(m.get('mae'), money=True)} | {_fmt(m.get('interval80_coverage'), pct=True)} |")
    lines += ["", "## Ajánlások találati pontossága", "",
              "Nem mérhető: nincs olyan ellenőrző adat (később realizált eladás / továbbértékesítés), amely "
              "megmutatná, hogy egy ajánlott vétel valóban nyereséges lett. A `python -m porcelan evaluate-recommendations` "
              "parancs ezt méri, amint lezárult aukciók vagy importált eladások kapcsolódnak korábban ajánlott hirdetésekhez.",
              "", "## Korlátok", "",
              "- A kínálati ár nem bizonyított piaci érték; a kínálati áron tanított modell a *hirdetési árszintet* becsüli.",
              "- A metrikák a tesztsorok számához képest bizonytalanok; kis n mellett (különösen US) csak irányt mutatnak.",
              "- Képi jellemzők csak akkor hatnak, ha a tanítóadatban van letöltött kép; ennek száma fent szerepel.",
              "- Az eredetiséget és az állapotot a modell nem igazolja."]
    return "\n".join(lines) + "\n"
