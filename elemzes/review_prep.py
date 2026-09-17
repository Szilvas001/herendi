"""Kézi ellenőrzéshez: a kiválasztott tételek leírása, sajátosságai és fotói.

Használat: python review_prep.py <likvid.json> <cache_dir> <kimeneti_mappa> [max_tétel] [kép/tétel]
A tételeket nettó haszon szerint csökkenő sorrendben dolgozza fel.
"""
import gzip, hashlib, json, re, subprocess, sys
from pathlib import Path
from bs4 import BeautifulSoup

src, cache, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
max_items = int(sys.argv[4]) if len(sys.argv) > 4 else 25
max_imgs = int(sys.argv[5]) if len(sys.argv) > 5 else 3
out.mkdir(parents=True, exist_ok=True)

items = json.loads(src.read_text(encoding="utf-8"))["tetelek"]
items.sort(key=lambda x: -x["netto_haszon_usd"])
report = []
for it in items[:max_items]:
    lid, url = it["listing_id"], it["url"]
    f = cache / f"{hashlib.sha1(url.encode()).hexdigest()}.html.gz"
    html = gzip.open(f, "rt", encoding="utf-8").read() if f.exists() else ""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    txt = re.sub(r"\s+", " ", soup.get_text(" "))
    feat = re.search(r"Termék sajátosságai (.*?)(?: bid| fix_price)? Mennyiség", txt)
    desc = re.search(r"Eladó leírása a termékről (.*?) Szállítási feltételek", txt)
    imgs = sorted(set(re.findall(r'https://images\.vatera\.hu/listings/[^"\s]+?' + lid + r'_(\d+)\.jpg', html)), key=int)
    base = re.search(r'(https://images\.vatera\.hu/listings/[^"\s]+?' + lid + r')_\d+\.jpg', html)
    d = out / lid
    d.mkdir(exist_ok=True)
    got = []
    if base:
        for n in imgs[:max_imgs]:
            p = d / f"img{n}.jpg"
            subprocess.run(["curl", "-s", "--max-time", "30", "-A", "Mozilla/5.0 Chrome/126", "-o", str(p),
                            f"{base.group(1)}_{n}.jpg?format=auto&resize.width=900"])
            got.append(str(p))
    report.append({**it, "sajatossagok": feat.group(1)[:400] if feat else None,
                   "leiras": desc.group(1)[:900] if desc else None, "kepek_osszesen": len(imgs), "kepek": got})
(out / "review.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
for r in report:
    print(f"## {r['listing_id']} | {r['modell']} | {r['vatera_huf']} Ft | ask {r['ask_usd']} USD | haszon {r['netto_haszon_usd']} USD ({r['arres_pct']}%) | {r['comps_txt']}")
    print(f"   CÍM: {r['title']}")
    print(f"   J: {r['sajatossagok']}")
    print(f"   L: {(r['leiras'] or '')[:600]}")
    print(f"   képek: {r['kepek_osszesen']} db, letöltve: {len(r['kepek'])}")
