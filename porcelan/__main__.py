"""Parancssor:  python -m porcelan <parancs>

Gyakori folyamat:
  python -m porcelan setup-models         # CLIP-súlyok letöltése (GitHub, SHA-256 ellenőrzés)
  python -m porcelan import-repo          # a repóban lévő 2026-09-i valós Vatera-adatok importja
  python -m porcelan crawl --source vatera  # teljes, folytatható bejárás (megszakítás után folytatja)
  python -m porcelan images               # képletöltés, duplikátumszűrés, CLIP-beágyazás, képi előszűrés
  python -m porcelan train                # reprodukálható tanítás + értékelés → models/<verzió>/
  python -m porcelan score                # becslések (csak változott hirdetésekre)
  python -m porcelan serve                # dashboard: http://127.0.0.1:8000
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _print(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python -m porcelan", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("crawl", help="adatgyűjtés egy forrásból (folytatható)")
    c.add_argument("--source", default="vatera", choices=["vatera", "jofogas"])
    c.add_argument("--full-catalog", action="store_true", help="a teljes nyilvános kategóriafa bejárása is")
    c.add_argument("--max-requests", type=int)
    c.add_argument("--time-budget", type=float, help="másodperc")
    c.add_argument("--no-resume", action="store_true", help="új bejárás a félbemaradt folytatása helyett")
    c.add_argument("--offline-dir", type=Path, help="mentett HTML-ek (teszt/demó)")

    sub.add_parser("import-repo", help="a repóban tárolt valós adatok importja")
    ic = sub.add_parser("import-csv", help="régi run.py CSV (vatera_osszes.csv stb.) importja")
    ic.add_argument("paths", nargs="+", type=Path)
    ip = sub.add_parser("import-prices", help="ár-CSV (realizált / leütési / kínálati árak) importja")
    ip.add_argument("paths", nargs="+", type=Path)
    sub.add_parser("import-ebay", help="eBay Browse API (EBAY_CLIENT_ID/SECRET szükséges)")
    im = sub.add_parser("images", help="képletöltés, dedup, CLIP-beágyazás, képi előszűrés")
    im.add_argument("--limit", type=int)
    sub.add_parser("setup-models", help="CLIP-súlyok letöltése és ellenőrzése")
    t = sub.add_parser("train", help="tanítás és értékelés")
    t.add_argument("--seed", type=int, default=42)
    t.add_argument("--seeds", type=int, default=5, help="ensemble-tagok száma")
    t.add_argument("--no-clip", action="store_true")
    s = sub.add_parser("score", help="becslések frissítése")
    s.add_argument("--force", action="store_true")
    sub.add_parser("pipeline", help="bejárás → képek → becslés (egy lépésben)")
    sub.add_parser("status", help="adat-, bejárás- és modellállapot")
    sub.add_parser("evaluate-recommendations", help="ajánlások utólagos ellenőrzése")
    top = sub.add_parser("top", help="a legjobb találatok a parancssorban")
    top.add_argument("--market", default="HU", choices=["HU", "US"])
    top.add_argument("--brand", choices=["Herendi", "Zsolnay"])
    top.add_argument("--max-price", type=int)
    top.add_argument("-n", type=int, default=15)
    sv = sub.add_parser("serve", help="dashboard indítása")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    rj = sub.add_parser("run-job", help=argparse.SUPPRESS)
    rj.add_argument("job_id", type=int)

    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    from . import db
    conn = db.get_conn()

    if a.cmd == "run-job":
        from . import jobs
        return jobs.run(a.job_id)
    if a.cmd == "crawl":
        from .crawler import Crawler
        from .net import Fetcher
        f = Fetcher(offline_dir=a.offline_dir) if a.offline_dir else None
        res = Crawler(a.source, conn, fetcher=f, full_catalog=a.full_catalog or None, max_requests=a.max_requests,
                      time_budget_sec=a.time_budget).run(resume=not a.no_resume)
        cov = res["coverage"]
        _print({"run_id": res["run_id"], "status": res["status"], "message": res["message"], "stats": res["stats"],
                "coverage": {k: v for k, v in cov.items() if k != "detail"}})
        return 0 if res["status"] in ("completed", "interrupted") else 2
    if a.cmd == "import-repo":
        from . import importers
        _print(importers.import_repo_snapshot(conn))
    elif a.cmd == "import-csv":
        from . import importers
        for path in a.paths:
            _print({str(path): importers.import_legacy_csv(path, conn=conn)})
    elif a.cmd == "import-prices":
        from . import importers
        for path in a.paths:
            _print({str(path): importers.import_price_csv(path, conn)})
    elif a.cmd == "import-ebay":
        from . import importers
        _print(importers.import_ebay_api(conn))
    elif a.cmd == "images":
        from . import images, vision
        _print({"download": images.download_pending(conn, limit=a.limit)})
        if vision.available():
            _print({"embedded": vision.embed_pending_images(conn), "prefilter": vision.visual_prefilter(conn)})
    elif a.cmd == "setup-models":
        from . import vision
        print(vision.ensure_weights(download=True))
        vision.load()
        print("CLIP betöltve.")
    elif a.cmd == "train":
        from .train import train
        man = train(conn, seed=a.seed, n_seeds=a.seeds, use_clip=not a.no_clip)
        print((Path(__import__("porcelan.settings", fromlist=["x"]).path("models_dir")) / man["version"]
               / "EVALUATION.md").read_text())
    elif a.cmd == "score":
        from .scoring import score
        _print(score(conn, force=a.force))
    elif a.cmd == "pipeline":
        from . import jobs
        _print(jobs.execute("pipeline", {}, lambda f, m: logging.info(m), conn))
    elif a.cmd == "status":
        from .api import status
        _print(status())
    elif a.cmd == "evaluate-recommendations":
        from .scoring import evaluate_recommendations
        _print(evaluate_recommendations(conn))
    elif a.cmd == "top":
        from . import api
        api._load_model()

        class _Req:
            query_params: dict = {}
        res = api.deals(_Req(), market=a.market, brand=a.brand, max_price=a.max_price, min_discount=None,
                        min_profit=None, min_confidence=None, source=None, sale_type=None, only_recommended=False, only_candidates=False,
                        include_abstain=True, sort="score", limit=a.n, offset=0, min_price=None)
        for c in res["items"]:
            m = c["hu"] if a.market == "HU" else c["us"]
            print(f"{c['price_huf']:>9,} Ft  {c['sale_type']:6}  érték {m['value_huf']['q50']:>9,} Ft  "
                  f"konz. nyereség {m['conservative_profit_huf'] or 0:>9,} Ft  bizalom {m['confidence']:.0%}  "
                  f"{'AJÁNLOTT' if c['recommended'] else 'jelölt' if c['candidate'] else '-':8} {c['title'][:60]}\n    {c['url']}")
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("porcelan.api:app", host=a.host, port=a.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
