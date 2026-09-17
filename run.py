#!/usr/bin/env python3
"""Vatera Herendi/Zsolnay deal finder.

Futás:  python run.py
Lépések: 1) Vatera scrape -> 2) 3 külön CSV (aukció / fix / alku)
         -> 3) Claude Opus 5 elemzés (3 részben) -> 4) riport + deals CSV.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from porcelan import ai_review, config, report, storage, vatera
from porcelan.httpclient import HttpClient


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Vatera Herendi/Zsolnay deal finder")
    p.add_argument("--pages", type=int, default=config.MAX_PAGES,
                   help="találati oldalak száma keresőkifejezésenként")
    p.add_argument("--limit", type=int, default=None,
                   help="maximum ennyi hirdetést tölt le (teszteléshez)")
    p.add_argument("--workers", type=int, default=config.WORKERS,
                   help="párhuzamos letöltő szálak száma")
    p.add_argument("--brand", choices=["mind", "herendi", "zsolnay"], default="mind",
                   help="melyik márkára keressen (porcelan profilnál)")
    p.add_argument("--profile", choices=["porcelan", "likvid"], default="porcelan",
                   help="porcelan: Herendi/Zsolnay; likvid: csövek, szovjet/NDK optika, órák, távcsövek")
    p.add_argument("--out-dir", type=Path, default=config.OUT_DIR,
                   help="kimeneti könyvtár")
    p.add_argument("--no-ai", action="store_true",
                   help="csak scrape + CSV, Claude hívás nélkül")
    p.add_argument("--chunk-size", type=int, default=config.AI_CHUNK_SIZE,
                   help="hány hirdetés menjen egy Claude hívásba")
    p.add_argument("--offline-dir", type=Path, default=None,
                   help="hálózat helyett lementett HTML-ek innen (teszt/demó)")
    p.add_argument("--no-cache", action="store_true", help="lemez-cache kikapcsolása")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def select_terms(brand: str) -> list[str]:
    if brand == "herendi":
        return config.SEARCH_TERMS_HEREND
    if brand == "zsolnay":
        return config.SEARCH_TERMS_ZSOLNAY
    return config.SEARCH_TERMS


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    log = logging.getLogger("run")
    config.apply_profile(args.profile)

    print("=" * 70)
    print("  VATERA – HERENDI & ZSOLNAY DEAL FINDER")
    print("=" * 70)

    # 1) Scrape --------------------------------------------------------------
    client = HttpClient(ttl_sec=-1 if args.no_cache else None,
                        offline_dir=args.offline_dir)
    accepted, rejected = vatera.scrape(
        terms=select_terms(args.brand), max_pages=args.pages,
        limit=args.limit, workers=args.workers, client=client,
    )

    if not accepted:
        log.warning("Nem találtunk releváns hirdetést. "
                    "Ha a Vatera blokkolt (anti-bot), próbáld később / kevesebb szállal.")

    # 2) Szeparált tárolás ---------------------------------------------------
    buckets = vatera.split_by_sale_type(accepted)
    stamp = storage.timestamp()
    paths = storage.save_all(buckets, rejected, args.out_dir, stamp)
    run_dir = paths["run_dir"]

    print("\nEladási típusok szerinti bontás:")
    for sale_type in config.SALE_TYPES + [config.SALE_UNKNOWN]:
        count = len(buckets.get(sale_type, []))
        if count or sale_type in config.SALE_TYPES:
            print(f"  - {config.SALE_TYPE_LABELS[sale_type]:<26} {count:>4} db")
    print(f"  - Kiszűrt (review kell)      {len(rejected):>4} db")

    # 3) Claude Opus 5 elemzés ----------------------------------------------
    ai_result = None
    if args.no_ai:
        log.info("AI elemzés kihagyva (--no-ai).")
    elif not accepted:
        log.info("Nincs mit elemezni, AI hívás kihagyva.")
    else:
        print(f"\nClaude ({config.CLAUDE_MODEL}) elemzés – 3 külön részben...")
        try:
            ai_result = ai_review.analyse(buckets, chunk_size=args.chunk_size)
        except ai_review.AiUnavailable as exc:
            log.warning("AI elemzés kihagyva: %s", exc)
        except Exception as exc:
            log.error("AI elemzés hiba: %s", exc)

    # 4) Riport --------------------------------------------------------------
    print("\nRiport készítése...")
    if ai_result:
        report.write_deals_csv(run_dir / "deals.csv", ai_result["talalatok"])
        storage.write_json(run_dir / "ai_nyers.json", ai_result)
    report_path = report.write_markdown(run_dir / "riport.md", buckets, rejected, ai_result)

    print("\n" + "=" * 70)
    print(f"KÉSZ. Minden kimenet: {run_dir}")
    print(f"  Riport: {report_path}")
    if ai_result:
        print(f"  Javaslatok: {len(ai_result['talalatok'])} db (deals.csv)")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
