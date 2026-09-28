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


class Prepared:
    """Egyszer kiszámított adat és jellemzők (tanításhoz és tanulási görbéhez)."""


def prepare(conn, seed: int, use_clip: bool, progress, train_mask_override=None) -> Prepared:
    P = Prepared()
    ds = dataset.build(conn)
    df = ds.df
    hz = (df.corpus == "herend_zsolnay").values
    if hz.sum() < 50:
        raise RuntimeError(f"Túl kevés Herendi/Zsolnay tanítóadat ({hz.sum()} sor). Importálj vagy gyűjts adatot előbb.")
    labels, split_info = dataset.split(df, seed)
    P.ds, P.df, P.labels, P.split_info = ds, df, labels, split_info
    P.tr, P.va, P.te = (labels == "train").values, (labels == "val").values, (labels == "test").values
    P.pt = (labels == "pretrain").values
    P.y = df.y_log.values.astype(np.float32)
    P.market_idx = np.array([MARKETS.index(m) for m in df.market])
    progress(0.08, f"Jellemzők: {len(df)} sor ({int(P.pt.sum())} előtanító), TF-IDF, strukturált, CLIP")
    P.pipe = FeaturePipeline(use_clip=use_clip).fit(df[P.tr | P.pt], conn)
    P.blocks = P.pipe.transform(df, conn)
    P.use_clip = use_clip
    P.y_mean = {m: float(P.y[P.tr & (df.market == m).values].mean())
                for m in MARKETS if (P.tr & (df.market == m).values).any()}
    return P


def build_design(P: Prepared, train_rows: np.ndarray):
    """kNN-jellemzők a megadott tanítósorokból építve (a görbéhez részhalmazra is), + mátrixok."""
    retr = Retrieval(_sub(P.blocks, train_rows), P.df[train_rows])
    knn = knn_block(retr, P.blocks, P.df, P.y[train_rows], P.y_mean)
    X, image_slice = design(P.blocks, knn, P.use_clip)
    Xg = np.concatenate([P.blocks["struct"], P.blocks["tfidf"], knn], axis=1)
    Xn = np.concatenate([P.blocks["struct"], P.blocks["tfidf"], knn], axis=1).astype(np.float32)
    return knn, X, Xg, Xn, image_slice


def train(conn=None, seed: int = 42, n_seeds: int = 5, use_clip: bool = True, progress=None,
          models_dir: Path | None = None) -> dict:
    t0 = time.time()
    progress = progress or (lambda f, m: log.info(m))
    conn = conn or db.get_conn()
    np.random.seed(seed)
    progress(0.02, "Tanítóadat összeállítása")
    P = prepare(conn, seed, use_clip, progress)
    df, y, tr, va, te, pt, market_idx = P.df, P.y, P.tr, P.va, P.te, P.pt, P.market_idx
    knn, X, Xg, Xn, image_slice = build_design(P, tr | pt)

    results: dict = {"val": {}, "test": {}, "test_by_brand": {}, "test_with_images": {}, "calibration": {}}
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

    progress(0.35, "Multimodális neurális modell (csak Herendi/Zsolnay adaton)")
    deep = DeepModel(n_seeds=n_seeds, image_slice=image_slice).fit(
        X[tr], y[tr], market_idx[tr], X[va], y[va], market_idx[va], seed=seed, log=log.info)
    models["deep_multimodal"] = ("deep", deep)
    pretrained = None
    if pt.sum() >= 500:
        progress(0.45, f"Előtanítás az általános porcelán/kerámia korpuszon ({int(pt.sum())} sor)")
        both = pt | tr
        pre = DeepModel(n_seeds=n_seeds, image_slice=image_slice).fit(
            X[both], y[both], market_idx[both], X[va], y[va], market_idx[va], seed=seed, log=log.info)
        progress(0.55, "Finomhangolás Herendi/Zsolnay adaton")
        pretrained = DeepModel(n_seeds=n_seeds, image_slice=image_slice).fit(
            X[tr], y[tr], market_idx[tr], X[va], y[va], market_idx[va], seed=seed, log=log.info,
            init=pre, lr=3e-4)
        models["deep_pretrained_ft"] = ("deep", pretrained)
    if use_clip:
        progress(0.6, "Ablation: neurális modell CLIP nélkül")
        deep_nc = DeepModel(n_seeds=n_seeds).fit(Xn[tr], y[tr], market_idx[tr], Xn[va], y[va], market_idx[va],
                                                 seed=seed, log=log.info)
        models["deep_no_clip"] = ("deep_nc", deep_nc)
        n_img = int(P.df[tr].has_image.sum())
        if n_img >= 100:
            progress(0.65, f"Ablation: ugyanaz a modell kép nélkül ({n_img} képes tanítósor)")
            ref = pretrained or deep
            deep_ni = DeepModel(n_seeds=n_seeds).fit(
                X[tr], y[tr], market_idx[tr], X[va], y[va], market_idx[va], seed=seed, log=log.info,
                init=None if ref is deep else pre, lr=1e-3 if ref is deep else 3e-4, zero_cols=image_slice)
            models["deep_no_image"] = ("deep", deep_ni)

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
    has_img = P.df.has_image.values
    for name, (kind, obj) in models.items():
        for market in MARKETS:
            vsub, pv = predict(kind, obj, va, market)
            tsub, pt_ = predict(kind, obj, te, market)
            if vsub.sum() == 0:
                continue
            ok = ~np.isnan(pv[:, 1])
            off = conformal_offset(pv[ok], y[vsub][ok])
            pv_c, pt_c = apply_offset(pv, off), apply_offset(pt_, off)
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
            im = has_img[tsub]
            if im.sum() >= 5:
                results["test_with_images"][f"{name}/{market}"] = metrics(pt_c[im], y[tsub][im])

    # Modellválasztás piaconként a VALIDÁCIÓS pinball alapján (a teszt érintetlen).
    chosen = {}
    for market in MARKETS:
        cands = [(results["val"][f"{n}/{market}"].get("pinball", np.inf), n) for n in models
                 if f"{n}/{market}" in results["val"] and results["val"][f"{n}/{market}"].get("n")
                 and results["val"][f"{n}/{market}"].get("coverage_pct", 0) >= 99]
        if cands:
            chosen[market] = min(cands)[1]

    ds = P.ds
    status, reasons = validation_gate(ds, results, chosen, P)
    version = f"v{datetime.now(timezone.utc):%Y%m%d-%H%M}-{dataset.fingerprint(df)[:8]}"
    out = Path(models_dir or settings.path("models_dir")) / version
    out.mkdir(parents=True, exist_ok=True)

    progress(0.9, "Mentés")
    hz = (df.corpus == "herend_zsolnay").values
    with (out / "pipeline.pkl").open("wb") as fh:
        pickle.dump(P.pipe, fh)
    (out / "baseline.json").write_text(json.dumps(base.state(), ensure_ascii=False))
    with (out / "gbm.pkl").open("wb") as fh:
        pickle.dump(gbms, fh)
    deep.save(out / "deep.pt")
    for name in ("deep_no_clip", "deep_pretrained_ft", "deep_no_image"):
        if name in models:
            models[name][1].save(out / f"{name}.pt")
    # a becsléshez csak a Herendi/Zsolnay sorok indexe kell (kNN és összehasonlító tételek)
    np.savez_compressed(out / "index.npz", **{k: v[hz].astype(np.float16) for k, v in P.blocks.items()},
                        knn=knn[hz], y=y[hz], split=np.asarray(P.labels[hz].tolist(), dtype="U8"))
    dataset.export(df[hz], out / "training_data.csv.gz", P.labels[hz])

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
        "train_rows": {"hz_train": int(tr.sum()), "pretrain": int(pt.sum()),
                       "hz_train_with_images": int(P.df[tr].has_image.sum()),
                       "by_market": {m: int((tr & (df.market == m).values).sum()) for m in MARKETS}},
        "target_basis": ds.basis,
        "target_currency": dataset.CURRENCY,
        "split": P.split_info,
        "y_mean": P.y_mean,
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


def _group_subsample(df: pd.DataFrame, mask: np.ndarray, frac: float, seed: int) -> np.ndarray:
    groups = sorted(set(df.group[mask]))
    rng = np.random.default_rng(seed)
    rng.shuffle(groups)
    keep = set(groups[:max(1, int(round(len(groups) * frac)))])
    return mask & df.group.isin(keep).values


def fit_power_law(ns, errs) -> dict | None:
    """err(n) ≈ a·n^(-b) + c illesztés (c rácson, a,b log-lineáris regresszióval)."""
    ns, errs = np.asarray(ns, float), np.asarray(errs, float)
    if len(ns) < 3 or np.any(errs <= 0):
        return None
    best = None
    for c in np.linspace(0, errs.min() * 0.95, 40):
        yy = np.log(errs - c)
        A = np.vstack([np.ones_like(ns), np.log(ns)]).T
        coef, *_ = np.linalg.lstsq(A, yy, rcond=None)
        sse = float(((A @ coef - yy) ** 2).sum())
        if coef[1] < 0 and (best is None or sse < best[0]):
            best = (sse, float(np.exp(coef[0])), float(-coef[1]), float(c))
    if not best:
        return None
    _, a, b, c = best
    return {"a": a, "b": b, "c": c}


def rows_needed(fit: dict | None, target: float) -> float | None:
    if not fit or target <= fit["c"]:
        return None
    return float(((target - fit["c"]) / fit["a"]) ** (-1 / fit["b"]))


def learning_curve(conn=None, seed: int = 42, fractions=(0.1, 0.25, 0.5, 1.0), use_clip: bool = True,
                   n_seeds: int = 2, progress=None, out_dir: Path | None = None) -> dict:
    """Hogyan javul a hiba a tanítóadat mennyiségével? (azonos teszthalmazon)

    Minden arányra a Herendi/Zsolnay tanítócsoportok véletlen részhalmazán tanul
    (a kNN-index is csak abból épül), és ugyanazon a teszthalmazon mér. Ha van
    általános korpusz, az előtanított változatot is méri. A hatványtörvény-illesztés
    alapján becsüli, hány tanítósor kellene a cél-MdAPE eléréséhez – ez extrapoláció,
    nem ígéret."""
    progress = progress or (lambda f, m: log.info(m))
    conn = conn or db.get_conn()
    P = prepare(conn, seed, use_clip, progress)
    df, y = P.df, P.y
    rows = []
    for fi, frac in enumerate(fractions):
        sub = _group_subsample(df, P.tr, frac, seed)
        variants = [("hz_only", sub)]
        if P.pt.sum() >= 500:
            variants.append(("pretrained", sub | P.pt))
        for vname, train_rows in variants:
            progress(fi / len(fractions), f"Tanulási görbe: {frac:.0%} ({int(sub.sum())} sor), {vname}")
            knn, X, Xg, Xn, image_slice = build_design(P, train_rows)
            if vname == "pretrained":
                pre = DeepModel(n_seeds=n_seeds, image_slice=image_slice).fit(
                    X[train_rows], y[train_rows], P.market_idx[train_rows], X[P.va], y[P.va], P.market_idx[P.va],
                    seed=seed, log=log.debug)
                m = DeepModel(n_seeds=n_seeds, image_slice=image_slice).fit(
                    X[sub], y[sub], P.market_idx[sub], X[P.va], y[P.va], P.market_idx[P.va], seed=seed,
                    log=log.debug, init=pre, lr=3e-4)
            else:
                m = DeepModel(n_seeds=n_seeds, image_slice=image_slice).fit(
                    X[sub], y[sub], P.market_idx[sub], X[P.va], y[P.va], P.market_idx[P.va], seed=seed, log=log.debug)
            for market in MARKETS:
                t = P.te & (df.market == market).values
                v = P.va & (df.market == market).values
                if not t.any() or not (sub & (df.market == market).values).any():
                    continue
                pv = m.predict(X[v], market)
                off = conformal_offset(pv, y[v])
                res = metrics(apply_offset(m.predict(X[t], market), off), y[t])
                rows.append({"fraction": frac, "variant": vname, "market": market,
                             "train_rows": int((sub & (df.market == market).values).sum()),
                             "pretrain_rows": int(P.pt.sum()) if vname == "pretrained" else 0,
                             "test_n": res["n"], "mdape": res["mdape"], "mae": res["mae"],
                             "interval80_coverage": res["interval80_coverage"]})
    target = settings.get("validation.max_mdape")
    fits = {}
    for market in MARKETS:
        for vname in ("hz_only", "pretrained"):
            pts = [(r["train_rows"], r["mdape"]) for r in rows if r["market"] == market and r["variant"] == vname]
            if len(pts) >= 3:
                fit = fit_power_law([p[0] for p in pts], [p[1] for p in pts])
                test_n = min(r["test_n"] for r in rows if r["market"] == market and r["variant"] == vname)
                max_rows = max(p[0] for p in pts)
                reliable = test_n >= 50 and max_rows >= 300
                fits[f"{market}/{vname}"] = {"fit": fit, "rows_for_target_mdape": rows_needed(fit, target),
                                             "target_mdape": target, "reliable": reliable, "test_n": test_n,
                                             "max_train_rows": max_rows}
    result = {"created_at": db.now_iso(), "split": P.split_info, "rows": rows, "fits": fits,
              "note": "Extrapoláció kevés pontból: nagyságrendi becslés, nem ígéret."}
    out_dir = Path(out_dir or (settings.path("models_dir") / "learning_curve"))
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "learning_curve.json").write_text(json.dumps(result, ensure_ascii=False, indent=1, default=float))
    (out_dir / "LEARNING_CURVE.md").write_text(learning_curve_markdown(result), encoding="utf-8")
    progress(1.0, "Tanulási görbe kész")
    return result


def learning_curve_markdown(r: dict) -> str:
    lines = ["# Tanulási görbe – mennyi adat kell?", "",
             f"Készült: {r['created_at']}. Teszthalmaz: {r['split']['test']}.", "",
             "| Változat | Piac | Tanítósor | Tesztminta | MdAPE | MAE | 80%-os lefedettség |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for x in r["rows"]:
        vn = "csak Herendi/Zsolnay" if x["variant"] == "hz_only" else f"előtanítva (+{x['pretrain_rows']} általános)"
        lines.append(f"| {vn} | {x['market']} | {x['train_rows']} | {x['test_n']} | {100 * x['mdape']:.1f}% | "
                     f"{x['mae']:,.0f} | {100 * x['interval80_coverage']:.0f}% |".replace(",", " "))
    lines += ["", "## Extrapoláció (MdAPE ≈ a·n^(−b) + c)", ""]
    for k, v in r["fits"].items():
        f = v["fit"]
        if not f:
            lines.append(f"- {k}: nem illeszthető (a hiba nem csökken monoton).")
            continue
        need = v["rows_for_target_mdape"]
        if not v.get("reliable", True):
            lines.append(f"- {k}: MEGBÍZHATATLAN extrapoláció (tesztminta {v.get('test_n')}, legfeljebb "
                         f"{v.get('max_train_rows')} tanítósor) – nincs értelmes becslés.")
            continue
        lines.append(f"- {k}: a={f['a']:.3g}, b={f['b']:.3f}, aszimptota c={100 * f['c']:.1f}% → "
                     + (f"~{need:,.0f} tanítósor kellene {100 * v['target_mdape']:.0f}% MdAPE-hez".replace(",", " ")
                        if need else f"a {100 * v['target_mdape']:.0f}%-os cél ezzel az adattípussal nem érhető el "
                                     f"(az aszimptota felette van) – jobb minőségű adat (kép, realizált ár) kell"))
    lines += ["", r["note"]]
    return "\n".join(lines) + "\n"


def validation_gate(ds, results: dict, chosen: dict, P=None) -> tuple[str, list[str]]:
    cfg = settings.get("validation")
    reasons = []
    if P is not None:
        n_img = int(P.df[P.tr].has_image.sum())
        if n_img < cfg.get("min_train_rows_with_images", 0):
            reasons.append(f"képes Herendi/Zsolnay tanítósor: {n_img} < {cfg['min_train_rows_with_images']} "
                           f"(képalapú becsléshez sok tízezer képes adat kell)")
        for market in dataset.MARKETS:
            n = int((P.tr & (P.df.market == market).values).sum())
            if n < cfg.get("min_train_rows_per_market", 0):
                reasons.append(f"{market}: {n} tanítósor < {cfg['min_train_rows_per_market']}")
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
              f"- Korpusz × piac: " + ", ".join(f"{k}: {v}" for k, v in ds.get("by_corpus_market", {}).items()),
              f"- Herendi/Zsolnay tanítósor: {man.get('train_rows', {}).get('hz_train')} "
              f"(ebből képes: {man.get('train_rows', {}).get('hz_train_with_images')}); "
              f"általános előtanító sor: {man.get('train_rows', {}).get('pretrain')} "
              f"(képes: {ds.get('general_with_images', 0)})",
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
    if r.get("test_with_images"):
        lines += ["", "## Csak a képes tesztsorokon (a kép hatása)", "",
                  "| Modell | Piac | n | MdAPE | MAE |", "|---|---|---:|---:|---:|"]
        for key, m in r["test_with_images"].items():
            name, market = key.split("/")
            lines.append(f"| {name} | {market} | {m.get('n', 0)} | {_fmt(m.get('mdape'), pct=True)} | "
                         f"{_fmt(m.get('mae'), money=True)} |")
        lines.append("")
        lines.append("A `deep_no_image` ugyanaz a modell a képjellemzők nélkül: a különbség a kép hozzájárulása.")
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
