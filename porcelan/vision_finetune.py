"""A CLIP képenkóder finomhangolása árbecslésre (nagy, képes tanítóadatra).

    python -m porcelan finetune-vision [--epochs 3] [--unfreeze 2] [--batch 64]

- Az előtanított OpenCLIP ViT-B/32 utolsó `unfreeze` transzformer-blokkja, a
  ln_post és a vetítés tanul; a többi fagyasztott (nem tanítunk nulláról).
- Rajta piaconkénti (HU/US) kvantilisfej: q10/q50/q90 log-ár, pinball-veszteség.
- Tanítóhalmaz: a Herendi/Zsolnay 'train' és az általános 'pretrain' sorok képei;
  korai megállás a Herendi/Zsolnay 'val' képein. A teszthalmazt nem látja.
- Kimenet: models/vision/<verzió>/ (visual_ft.pt, head.pt, manifest.json) és
  models/vision/CURRENT; utána az összes kép újrabeágyazása a finomhangolt
  enkóderrel (külön címkével), amit a becslőmodell következő tanítása használ.

Érdemi eredményhez sok tízezer képes sor és GPU kell. CPU-n csak kis próbára való.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import dataset, db, settings, vision
from .model import MARKETS, QUANTILES, metrics

log = logging.getLogger(__name__)


def _image_paths(conn, df) -> list[str | None]:
    """Soronként az első (eredeti, nem duplikátum) kép elérési útja."""
    base = settings.path("image_dir")
    out = []
    for lid, rid in zip(df.listing_id, df["id"]):
        row = None
        if lid is not None and lid == lid:
            row = conn.execute("SELECT COALESCE(o.path, i.path) p FROM images i LEFT JOIN images o ON o.id=i.dup_of "
                               "WHERE i.listing_id=? AND i.status IN ('ok','duplicate') ORDER BY i.position LIMIT 1",
                               (int(lid),)).fetchone()
        if row is None and rid is not None and rid == rid:
            row = conn.execute("SELECT COALESCE(o.path, i.path) p FROM images i LEFT JOIN images o ON o.id=i.dup_of "
                               "WHERE i.price_record_id=? AND i.status IN ('ok','duplicate') ORDER BY i.position LIMIT 1",
                               (int(rid),)).fetchone()
        out.append(str(base / row["p"]) if row and row["p"] else None)
    return out


def finetune(conn=None, epochs: int = 3, unfreeze: int = 2, batch: int = 64, lr: float = 1e-5, seed: int = 42,
             max_images: int | None = None, progress=None, reembed: bool = True) -> dict:
    import open_clip
    import torch
    from PIL import Image

    progress = progress or (lambda f, m: log.info(m))
    conn = conn or db.get_conn()
    torch.manual_seed(seed)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    t0 = time.time()

    ds = dataset.build(conn)
    df = ds.df
    labels, split_info = dataset.split(df, seed)
    df = df.assign(split=labels.values, path=_image_paths(conn, df))
    df = df[df.path.notna()]
    tr = df[df.split.isin(["train", "pretrain"])]
    va = df[df.split == "val"]
    te = df[df.split == "test"]
    if max_images:
        tr = tr.sample(n=min(max_images, len(tr)), random_state=seed)
    if len(tr) < 20 or len(va) < 5:
        raise RuntimeError(f"Kevés képes tanítósor a finomhangoláshoz (train {len(tr)}, val {len(va)}). "
                           "Előbb gyűjts és tölts le képeket (harvest-ebay, crawl, images).")
    progress(0.02, f"Finomhangolás: {len(tr)} tanító-, {len(va)} validációs, {len(te)} tesztkép; eszköz: {dev}")

    base_model, preprocess_val, _ = vision.load()
    import copy
    model = copy.deepcopy(base_model).to(dev)
    visual = model.visual
    preprocess_train = open_clip.image_transform(visual.image_size, is_train=True)
    for p in model.parameters():
        p.requires_grad = False
    blocks = visual.transformer.resblocks
    trainable = list(blocks[-unfreeze:]) + [visual.ln_post]
    for m in trainable:
        for p in m.parameters():
            p.requires_grad = True
    if isinstance(getattr(visual, "proj", None), torch.nn.Parameter):
        visual.proj.requires_grad = True

    y_mean = np.array([tr[tr.market == m].y_log.mean() if (tr.market == m).any() else 0.0 for m in MARKETS],
                      np.float32)
    head = torch.nn.Linear(vision.DIM, 3 * len(MARKETS)).to(dev)
    q = torch.tensor(QUANTILES, device=dev)

    def forward(x):
        z = visual(x)
        z = z / z.norm(dim=-1, keepdim=True)
        o = head(z).view(-1, len(MARKETS), 3)
        mid = o[..., 1]
        return torch.stack([mid - torch.nn.functional.softplus(o[..., 0]), mid,
                            mid + torch.nn.functional.softplus(o[..., 2])], dim=-1)

    class DS(torch.utils.data.Dataset):
        def __init__(self, frame, tf):
            self.p = list(frame.path)
            self.y = (frame.y_log.values - y_mean[[MARKETS.index(m) for m in frame.market]]).astype(np.float32)
            self.m = np.array([MARKETS.index(m) for m in frame.market])
            self.tf = tf

        def __len__(self):
            return len(self.p)

        def __getitem__(self, i):
            try:
                img = self.tf(Image.open(self.p[i]).convert("RGB"))
            except OSError:
                img = torch.zeros(3, visual.image_size[0] if isinstance(visual.image_size, tuple)
                                  else visual.image_size, visual.image_size[-1] if isinstance(visual.image_size, tuple)
                                  else visual.image_size)
            return img, self.y[i], self.m[i]

    g = torch.Generator().manual_seed(seed)
    tl = torch.utils.data.DataLoader(DS(tr, preprocess_train), batch_size=batch, shuffle=True, generator=g,
                                     num_workers=2 if dev.type == "cuda" else 0)

    def predict(frame):
        dl = torch.utils.data.DataLoader(DS(frame, preprocess_val), batch_size=batch * 2, shuffle=False)
        preds = []
        model.eval()
        with torch.no_grad():
            for x, _, mi in dl:
                o = forward(x.to(dev)).cpu().numpy()
                preds.append(o[np.arange(len(mi)), mi.numpy()] + y_mean[mi.numpy()][:, None])
        return np.concatenate(preds) if preds else np.zeros((0, 3))

    def pinball(pred, y):
        return float(np.mean([np.mean(np.maximum(qq * (y - pred[:, i]), (qq - 1) * (y - pred[:, i])))
                              for i, qq in enumerate(QUANTILES)]))

    opt = torch.optim.AdamW([{"params": [p for p in model.parameters() if p.requires_grad], "lr": lr},
                             {"params": head.parameters(), "lr": lr * 100}], weight_decay=0.05)
    use_amp = dev.type == "cuda"
    scaler = torch.amp.GradScaler("cuda") if use_amp else None
    best, best_state, history = float("inf"), None, []
    steps = epochs * max(1, len(tl))
    step = 0
    for ep in range(epochs):
        model.train()
        for x, yb, mi in tl:
            x, yb, mi = x.to(dev), yb.to(dev), mi.to(dev)
            opt.zero_grad()
            with torch.autocast(device_type=dev.type, enabled=use_amp):
                sel = forward(x)[torch.arange(len(mi), device=dev), mi]
                diff = yb[:, None] - sel.float()
                loss = torch.maximum(q * diff, (q - 1) * diff).mean()
            if scaler:
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            else:
                loss.backward()
                opt.step()
            step += 1
            if step % 20 == 0:
                progress(0.05 + 0.75 * step / steps, f"epoch {ep + 1}/{epochs}, lépés {step}/{steps}, loss {float(loss):.4f}")
        pv = predict(va)
        vl = pinball(pv, va.y_log.values)
        history.append({"epoch": ep + 1, "val_pinball": vl})
        progress(0.05 + 0.75 * (ep + 1) / epochs, f"epoch {ep + 1}: val pinball {vl:.4f}")
        if vl < best:
            best = vl
            best_state = ({k: v.detach().cpu().clone() for k, v in visual.state_dict().items()
                           if any(k.startswith(pref) for pref in _trainable_prefixes(visual, unfreeze))},
                          {k: v.detach().cpu().clone() for k, v in head.state_dict().items()})
    visual.load_state_dict(best_state[0], strict=False)
    head.load_state_dict(best_state[1])

    # tisztán képalapú becslés mérése (Herendi/Zsolnay val és teszt, piaconként)
    res = {"val": {}, "test": {}}
    for name, frame in (("val", va), ("test", te)):
        if len(frame) == 0:
            continue
        pr = predict(frame)
        for m in MARKETS:
            mm = (frame.market == m).values
            if mm.sum() >= 3:
                res[name][m] = metrics(pr[mm], frame.y_log.values[mm])

    ver = f"vis{datetime.now(timezone.utc):%Y%m%d-%H%M}-{len(tr)}"
    out = settings.path("models_dir") / "vision" / ver
    out.mkdir(parents=True, exist_ok=True)
    torch.save(best_state[0], out / "visual_ft.pt")
    torch.save({"head": best_state[1], "y_mean": y_mean.tolist()}, out / "head.pt")
    manifest = {"version": ver, "created_at": db.now_iso(), "device": str(dev), "epochs": epochs,
                "unfreeze_blocks": unfreeze, "batch": batch, "lr": lr, "seed": seed,
                "train_images": len(tr), "val_images": len(va), "test_images": len(te),
                "train_images_by_corpus": {k: int(v) for k, v in tr.corpus.value_counts().items()},
                "history": history, "image_only_metrics": res, "split": split_info,
                "base_weights_sha256": settings.get("paths.clip_weights_sha256"),
                "seconds": round(time.time() - t0, 1),
                "note": "Tisztán képalapú becslés (a fej) mérése; a termék becslőmodellje a finomhangolt "
                        "képbeágyazást a szöveges és strukturált jellemzőkkel együtt használja."}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1, default=float))
    (out.parent / "CURRENT").write_text(ver + "\n")
    vision._ft_models.clear()
    if reembed:
        progress(0.85, "Képek újrabeágyazása a finomhangolt enkóderrel")
        manifest["reembedded"] = vision.embed_pending_images(conn, tag=f"ft-{ver}")
    progress(1.0, f"Kész: {ver}")
    return manifest


def _trainable_prefixes(visual, unfreeze: int) -> list[str]:
    n = len(visual.transformer.resblocks)
    return [f"transformer.resblocks.{i}." for i in range(n - unfreeze, n)] + ["ln_post.", "proj"]
