"""A vatera_osszes.csv tömörítése soronként egy hirdetésre, elemzéshez."""
import csv
import re
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
desc_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 0

rows = list(csv.DictReader((run_dir / "vatera_osszes.csv").open(encoding="utf-8-sig")))
rows.sort(key=lambda r: (r["brand"], r["sale_type"], -int(r["price_huf"] or 0)))

for r in rows:
    parts = [
        r["listing_id"],
        r["brand"][:1],
        {"aukcio": "AUK", "fix": "FIX", "alku": "ALK"}.get(r["sale_type"], "???"),
        f"{int(r['price_huf'] or 0):>8,}".replace(",", " "),
        f"L{r['bid_count']}" if r["sale_type"] == "aukcio" and r["bid_count"] else "",
        r["title"][:70],
    ]
    for key, tag in (("decor_hints", "D"), ("damage_flags", "S"), ("suspect_flags", "G")):
        if r[key]:
            parts.append(f"{tag}:{r[key]}")
    if desc_chars:
        parts.append("~ " + re.sub(r"\s+", " ", r["description"])[:desc_chars])
    print(" | ".join(p for p in parts if p))
print(f"# {len(rows)} sor", file=sys.stderr)
