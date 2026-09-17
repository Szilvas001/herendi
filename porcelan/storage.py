"""Tárolás: eladási típusonként külön CSV + összesítő CSV/JSON."""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

FIELDS = [
    "listing_id", "brand", "title", "sale_type", "sale_type_label", "offer_possible",
    "price_huf", "price_kind", "buy_now_huf", "start_bid_huf", "current_bid_huf",
    "bid_count", "end_time", "seller", "damage_flags", "suspect_flags",
    "decor_hints",
    "description", "url", "accepted", "reject_reason",
]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_csv(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(rec)
    log.info("   %-28s %4d sor", path.name, len(records))
    return path


def write_json(path: Path, payload) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("   %-28s", path.name)
    return path


def save_all(buckets: dict[str, list[dict]], rejected: list[dict],
             out_dir: Path, stamp: str | None = None) -> dict[str, Path]:
    """Kiírja a 3 (+1) eladási típus CSV-jét, az összesítőt és az elutasítottakat."""
    stamp = stamp or timestamp()
    run_dir = Path(out_dir) / f"run_{stamp}"
    paths: dict[str, Path] = {}

    log.info("Mentés ide: %s", run_dir)
    for sale_type in config.SALE_TYPES + [config.SALE_UNKNOWN]:
        records = buckets.get(sale_type, [])
        if not records and sale_type == config.SALE_UNKNOWN:
            continue
        paths[sale_type] = write_csv(run_dir / f"vatera_{sale_type}.csv", records)

    all_records = [r for t in buckets for r in buckets[t]]
    paths["osszes"] = write_csv(run_dir / "vatera_osszes.csv", all_records)
    if rejected:
        paths["elutasitott"] = write_csv(run_dir / "vatera_elutasitott.csv", rejected)
    paths["json"] = write_json(run_dir / "vatera_osszes.json", all_records)
    paths["run_dir"] = run_dir
    return paths
