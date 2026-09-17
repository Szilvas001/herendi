"""Végső kimenet: markdown riport + deals CSV a Claude javaslataiból."""
from __future__ import annotations

import csv
import logging
from datetime import datetime
from pathlib import Path

from . import config

log = logging.getLogger(__name__)

DEAL_FIELDS = [
    "kategoria", "bizalom", "marka", "sale_type", "cim", "ar_huf", "ar_huf_scrape",
    "becsult_ertek_eur_min", "becsult_ertek_eur_max", "allapot_jelzok",
    "indoklas", "kockazatok", "listing_id", "url",
]

KATEGORIA_LABEL = {
    "aron_aluli": "Áron aluli",
    "nyugati_piac": "Nyugati piacon jól eladható",
    "mindketto": "Áron aluli + nyugati piac",
}


def write_deals_csv(path: Path, picks: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=DEAL_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for pick in picks:
            writer.writerow(pick)
    log.info("   %-28s %4d sor", path.name, len(picks))
    return path


def _counts_line(buckets: dict[str, list[dict]]) -> str:
    parts = [f"{config.SALE_TYPE_LABELS[t]}: **{len(buckets.get(t, []))}**"
             for t in config.SALE_TYPES]
    return " | ".join(parts)


def write_markdown(path: Path, buckets: dict[str, list[dict]], rejected: list[dict],
                   ai_result: dict | None) -> Path:
    picks = (ai_result or {}).get("talalatok", [])
    lines: list[str] = []
    add = lines.append

    add("# Vatera – Herendi & Zsolnay deal riport")
    add("")
    add(f"Készült: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    add("")
    add("## 1. Scrape összefoglaló")
    add("")
    add(_counts_line(buckets))
    add("")
    total = sum(len(v) for v in buckets.values())
    add(f"- Releváns (Herendi/Zsolnay) hirdetés: **{total}**")
    add(f"- Kiszűrt (utánzat / nem porcelán / nem márkás): **{len(rejected)}**")
    brands: dict[str, int] = {}
    for records in buckets.values():
        for rec in records:
            brands[rec.get("brand") or "?"] = brands.get(rec.get("brand") or "?", 0) + 1
    if brands:
        add("- Márka szerint: " + ", ".join(f"{k}: {v}" for k, v in sorted(brands.items())))
    add("")

    add("## 2. Claude Opus 5 javaslatok")
    add("")
    if ai_result is None:
        add("_Az AI elemzés ki volt kapcsolva (`--no-ai`) vagy nem futott le._")
        add("")
    elif not picks:
        add("A modell egyetlen tételt sem talált áron alulinak vagy nyugati piacra valónak.")
        add("")
    else:
        add(f"Összesen **{len(picks)}** javaslat.")
        add("")
        for sale_type in config.SALE_TYPES:
            group = [p for p in picks if p.get("sale_type") == sale_type]
            if not group:
                continue
            add(f"### {config.SALE_TYPE_LABELS[sale_type]} ({len(group)} tétel)")
            add("")
            for pick in group:
                price = pick.get("ar_huf") or pick.get("ar_huf_scrape")
                price_txt = f"{price:,} Ft".replace(",", " ") if price else "ár ismeretlen"
                add(f"- **{pick.get('cim', '')}**  ")
                add(f"  {KATEGORIA_LABEL.get(pick.get('kategoria'), pick.get('kategoria'))} · "
                    f"bizalom: {pick.get('bizalom')} · {price_txt} · "
                    f"becsült nyugati ár: {pick.get('becsult_ertek_eur_min')}–"
                    f"{pick.get('becsult_ertek_eur_max')} EUR  ")
                if pick.get("allapot_jelzok"):
                    add(f"  Állapot jelzők: {pick['allapot_jelzok']}  ")
                add(f"  {pick.get('indoklas', '')}  ")
                if pick.get("kockazatok"):
                    add(f"  Kockázat: {pick['kockazatok']}  ")
                add(f"  <{pick.get('url', '')}>")
                add("")

    summaries = (ai_result or {}).get("osszegzesek", {})
    if summaries:
        add("## 3. Modell összegzések eladási típusonként")
        add("")
        for sale_type, text in summaries.items():
            if text:
                add(f"**{config.SALE_TYPE_LABELS[sale_type]}:** {text}")
                add("")

    errors = (ai_result or {}).get("hibak", [])
    if errors:
        add("## Hibák az AI hívás közben")
        add("")
        for err in errors:
            add(f"- {err}")
        add("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
    log.info("   %-28s", path.name)
    return path
