"""Háttérfeladatok: adatgyűjtés, import, képfeldolgozás, tanítás, pontozás.

A dashboard a `jobs` táblába ír egy sort, és külön folyamatot indít
(`python -m porcelan run-job <id>`), így a hosszú futás nem blokkolja a
webszervert. A folyamat a haladást a táblába írja; leállítás SIGTERM-mel
(a bejárás ilyenkor folytatható állapotban áll meg).
"""
from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import sys
import traceback
from pathlib import Path

from . import db, settings

log = logging.getLogger(__name__)
KINDS = ("crawl", "import_csv", "import_repo", "images", "train", "score", "pipeline")


def create(kind: str, params: dict | None = None, conn=None) -> int:
    if kind not in KINDS:
        raise ValueError(f"ismeretlen feladat: {kind}")
    conn = conn or db.get_conn()
    running = conn.execute("SELECT id FROM jobs WHERE kind=? AND status IN ('queued','running')", (kind,)).fetchone()
    if running:
        raise RuntimeError(f"Már fut ilyen feladat (#{running['id']}).")
    cur = conn.execute("INSERT INTO jobs(kind, params, status, created_at) VALUES(?,?, 'queued', ?)",
                       (kind, json.dumps(params or {}, ensure_ascii=False), db.now_iso()))
    conn.commit()
    return cur.lastrowid


def spawn(job_id: int) -> int:
    logs = settings.path("data_dir") / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / f"job_{job_id}.log"
    env = dict(os.environ)
    fh = open(log_path, "ab")
    proc = subprocess.Popen([sys.executable, "-m", "porcelan", "run-job", str(job_id)], cwd=settings.ROOT,
                            stdout=fh, stderr=subprocess.STDOUT, env=env, start_new_session=True)
    conn = db.get_conn()
    conn.execute("UPDATE jobs SET pid=?, log_path=? WHERE id=?", (proc.pid, str(log_path), job_id))
    conn.commit()
    return proc.pid


def cancel(job_id: int) -> bool:
    conn = db.get_conn()
    row = conn.execute("SELECT pid, status FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row or row["status"] not in ("queued", "running") or not row["pid"]:
        return False
    try:
        os.kill(row["pid"], signal.SIGTERM)
    except ProcessLookupError:
        conn.execute("UPDATE jobs SET status='failed', message='a folyamat nem fut' WHERE id=?", (job_id,))
        conn.commit()
        return False
    return True


def reap_dead(conn=None) -> None:
    """Megszakadt (pl. újraindított gépen maradt) 'running' sorok lezárása."""
    conn = conn or db.get_conn()
    for r in conn.execute("SELECT id, pid FROM jobs WHERE status='running'").fetchall():
        alive = False
        if r["pid"]:
            try:
                os.kill(r["pid"], 0)
                alive = True
            except (ProcessLookupError, PermissionError):
                alive = False
        if not alive:
            conn.execute("UPDATE jobs SET status='failed', message='a folyamat váratlanul leállt', finished_at=? "
                         "WHERE id=?", (db.now_iso(), r["id"]))
    conn.commit()


def run(job_id: int) -> int:
    """A külön folyamatban futó feladat törzse."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    conn = db.get_conn()
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    params = json.loads(job["params"] or "{}")
    conn.execute("UPDATE jobs SET status='running', started_at=?, pid=? WHERE id=?", (db.now_iso(), os.getpid(), job_id))
    conn.commit()

    def progress(frac: float, msg: str):
        conn.execute("UPDATE jobs SET progress=?, message=? WHERE id=?", (round(float(frac), 3), msg[:500], job_id))
        conn.commit()
        log.info("[%3.0f%%] %s", 100 * frac, msg)

    try:
        result = execute(job["kind"], params, progress, conn)
        status = "done"
        if isinstance(result, dict) and result.get("status") in ("blocked", "interrupted"):
            status = "done"
        msg = json.dumps(result, ensure_ascii=False, default=str)[:4000]
    except Exception as exc:
        status, msg = "failed", f"{exc}\n{traceback.format_exc()[-2000:]}"
        log.error(msg)
    conn.execute("UPDATE jobs SET status=?, message=?, progress=CASE WHEN ?='done' THEN 1 ELSE progress END, "
                 "finished_at=? WHERE id=?", (status, msg, status, db.now_iso(), job_id))
    conn.commit()
    return 0 if status == "done" else 1


def execute(kind: str, params: dict, progress, conn) -> dict:
    if kind == "crawl":
        from .crawler import Crawler
        c = Crawler(params.get("source", "vatera"), conn, full_catalog=params.get("full_catalog"),
                    max_requests=params.get("max_requests"), time_budget_sec=params.get("time_budget_sec"),
                    progress=progress)
        res = c.run(resume=params.get("resume", True))
        if res["status"] == "completed" or params.get("then_score", True):
            _post_crawl(progress, conn)
        return {k: res[k] for k in ("run_id", "status", "message")} | {"coverage": res["coverage"]["label"]}
    if kind == "import_csv":
        from . import importers
        path = Path(params["path"])
        if params.get("type") == "prices":
            return importers.import_price_csv(path, conn)
        res = importers.import_legacy_csv(path, conn=conn)
        _score_if_model(progress, conn)
        return res
    if kind == "import_repo":
        from . import importers
        res = importers.import_repo_snapshot(conn)
        _score_if_model(progress, conn)
        return res
    if kind == "images":
        return _images(progress, conn)
    if kind == "train":
        from .train import train
        man = train(conn, seed=params.get("seed", 42), n_seeds=params.get("n_seeds", 5), progress=progress)
        _score_if_model(progress, conn)
        return {"version": man["version"], "status": man["status"]}
    if kind == "score":
        from .scoring import score
        return score(conn, force=params.get("force", False), progress=progress)
    if kind == "pipeline":
        from .crawler import Crawler
        out = {}
        for src in params.get("sources", ["vatera"]):
            res = Crawler(src, conn, progress=progress, time_budget_sec=params.get("time_budget_sec")).run()
            out[src] = {"status": res["status"], "coverage": res["coverage"]["label"]}
        out["post"] = _post_crawl(progress, conn)
        return out
    raise ValueError(kind)


def _images(progress, conn) -> dict:
    from . import images, vision
    out = {"download": images.download_pending(conn, progress=progress)}
    if vision.available():
        out["embedded"] = vision.embed_pending_images(conn, progress)
        out["prefilter"] = vision.visual_prefilter(conn)
    else:
        out["embedded"] = "CLIP nem elérhető (python -m porcelan setup-models)"
    return out


def _score_if_model(progress, conn):
    from .predict import current_version
    if current_version():
        from .scoring import score
        return score(conn, progress=progress)
    return {"skipped": "nincs modell"}


def _post_crawl(progress, conn) -> dict:
    out = {"images": _images(progress, conn)}
    out["score"] = _score_if_model(progress, conn)
    return out
