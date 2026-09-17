"""riport/ mappa: README (összefoglaló + Claude válogatás) és eladási típusonként
külön fájl, minden hirdetés konkrét Vatera linkkel.

Használat: python build_report.py <run_dir> <picks.json> <kimeneti mappa>
picks.json: {"osszegzes": str, "modszer": str,
             "talalatok": [{listing_id, kategoria, bizalom, becsult_ertek_eur_min,
                            becsult_ertek_eur_max, indoklas, kockazatok}]}
"""
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

run_dir, picks_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
out_dir.mkdir(parents=True, exist_ok=True)

TYPES = [
    ("aukcio", "Aukció (licit)", "aukcio.md"),
    ("fix", "Fix áras", "fix-aras.md"),
    ("alku", "Alkuképes / irányáras", "alkukepes.md"),
    ("ismeretlen", "Ismeretlen típus", "ismeretlen.md"),
]
TYPE_LABEL = {t: lbl for t, lbl, _ in TYPES}
TYPE_FILE = {t: f for t, _, f in TYPES}
KAT_LABEL = {"aron_aluli": "Áron aluli", "nyugati_piac": "Nyugati piacon jól eladható",
             "mindketto": "Áron aluli + nyugati piac"}
BIZ_ORDER = {"magas": 0, "kozepes": 1, "alacsony": 2}
STAMP = datetime.now().strftime("%Y-%m-%d %H:%M")


def load(name):
    p = run_dir / name
    return list(csv.DictReader(p.open(encoding="utf-8-sig"))) if p.exists() else []


def cell(s):
    return (s or "").replace("|", "/").replace("\n", " ").strip()


def huf(v):
    return f"{int(v):,} Ft".replace(",", " ") if v else "–"


def flags(r):
    return "; ".join(f"{lbl}: {r[k]}" for k, lbl in (
        ("decor_hints", "minta"), ("damage_flags", "sérülés"), ("suspect_flags", "gyanú")) if r[k])


def write(name, lines):
    (out_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")


rows = load("vatera_osszes.csv")
rejected = load("vatera_elutasitott.csv")
by_id = {r["listing_id"]: r for r in rows}
picks = json.loads(picks_path.read_text(encoding="utf-8"))
missing = [p["listing_id"] for p in picks["talalatok"] if p["listing_id"] not in by_id]
if missing:
    raise SystemExit(f"Nem létező listing_id a válogatásban: {missing}")
sel = sorted(picks["talalatok"],
             key=lambda p: (BIZ_ORDER.get(p["bizalom"], 3), -p["becsult_ertek_eur_max"]))
picked = {p["listing_id"] for p in sel}
types = Counter(r["sale_type"] for r in rows)

# README.md: összefoglaló + válogatás ---------------------------------------------
L = []
add = L.append
add("# Vatera – Herendi & Zsolnay deal riport")
add("")
add(f"Készült: {STAMP} · forrás: vatera.hu élő scrape (`python run.py --no-ai`), "
    "elemzés: Claude (Claude Code munkamenetben)")
add("")
add("## Fájlok ebben a mappában")
add("")
add("| Fájl | Tartalom | db |")
add("|---|---|---:|")
add(f"| [README.md](README.md) | összefoglaló + Claude válogatás (áron aluli / nyugati piac) | {len(sel)} |")
for t, lbl, fname in TYPES:
    if types.get(t):
        add(f"| [{fname}]({fname}) | az összes {lbl.lower()} hirdetés, linkkel | {types[t]} |")
add(f"| [kiszurt.md](kiszurt.md) | kiszűrt hirdetések (utánzat, nem porcelán…) okkal | {len(rejected)} |")
add("")
add("## Összefoglaló")
add("")
add("Márka szerint: " + ", ".join(f"{k}: {v}" for k, v in sorted(Counter(r['brand'] for r in rows).items())))
add("")
if picks.get("osszegzes"):
    add(picks["osszegzes"])
    add("")
likvid_path = Path(sys.argv[5]) if len(sys.argv) > 5 else None
if likvid_path:
    lk = json.loads(likvid_path.read_text(encoding="utf-8"))
    base = likvid_path.parent
    liq_hz = json.loads((base / "liquidity.json").read_text(encoding="utf-8"))
    pl2_hz = json.loads((base / "placement2.json").read_text(encoding="utf-8"))

    def fmt(v, c="USD"):
        return f"{int(v):,} {c}".replace(",", " ")

    def weeks(txt):
        nums = [int(x) for x in re.findall(r"\d+", txt)]
        mult = 4.3 if "hónap" in txt else 1
        return (nums[0] * mult, nums[-1] * mult)

    table = []
    for it in lk["tetelek"]:
        db = f" ({it['db']} db)" if it["db"] > 1 else ""
        table.append({
            "sort": weeks(it["ask_ido"]) + (weeks(it["floor_ido"])[0], -it["arres_pct"]),
            "cells": [f"[{cell(it['title'])}]({it['url']}){db}", f"{it['kategoria']} · {it['modell']}",
                      f"{huf(it['vatera_huf'])} (≈ {fmt(it['koltseg_usd'])})", f"{fmt(it['ask_usd'])} · eBay.com",
                      it["ask_ido"], it["ask_liq"], fmt(it["floor_usd"]), f"{it['floor_ido']}, {it['floor_liq']}",
                      f"{fmt(it['netto_haszon_usd'])} ({it['arres_pct']}%)", it["comps_txt"], "**Ajánlott**"]})
    for lid, T in pl2_hz["tetelek"].items():
        if T["ertekeles"] != "Ajánlott" or lid not in by_id:
            continue
        L2, r = liq_hz[lid], by_id[lid]
        net = round(L2["ask"] * (1 - {"eBay.com": .15, "eBay.de": .13, "Etsy": .12, "Catawiki": .125}[L2["platform"]]) - L2["koltseg"])
        table.append({
            "sort": weeks(T["ask_ido"]) + (weeks(T["floor_ido"])[0], -round(100 * net / L2["koltseg"])),
            "cells": [f"[{cell(r['title'])}]({r['url']})", f"{r['brand']} porcelán",
                      f"{huf(r['price_huf'])} (≈ {fmt(L2['koltseg'], L2['cur'])})", f"{fmt(L2['ask'], L2['cur'])} · {L2['platform']}",
                      T["ask_ido"], T["ask_liq"], fmt(L2["floor"], L2["cur"]), f"{T['floor_ido']}, {T['floor_liq']}",
                      f"{fmt(net, L2['cur'])} ({round(100 * net / L2['koltseg'])}%)", L2["comps_txt"], f"**{T['ertekeles']}**"]})
    table.sort(key=lambda x: x["sort"])
    st = lk["stats"]
    add("## Likvid, nagy árrésű tételek nyugati eladásra – összesített táblázat")
    add("")
    add(f"A Herendi és Zsolnay tételek mellett a Vaterán jellemző, nyugaton gyorsan forgó termékeket is átvizsgáltam: Tungsram elektroncsöveket, szovjet, NDK és japán objektíveket (Helios, Jupiter, Carl Zeiss Jena, Meyer-Optik, Takumar, Nikkor), filmes fényképezőgépeket (Rolleiflex, Contax, Olympus, Canon, Nikon, Pentax, Yashica, Lomo, Kiev, Zenit), órákat (Poljot 3133 változatok, Vostok, Raketa, Seiko, Junghans), retró elektronikát (Walkman, Game Boy, Nintendo, Sega, Commodore, Amiga, Atari), töltőtollakat (Pelikan, Parker) és Carl Zeiss Jena távcsöveket, 101 keresőszóval. A {st['osszes']} elfogadott hirdetésből {st['kivalasztva']} felelt meg minden feltételnek. A táblázatban ezek és a korábbi ajánlott Herendi/Zsolnay tételek szerepelnek, **a kezdő áron becsült eladási idő szerint rendezve, a leggyorsabbal kezdve**.")
    add("")
    add("**Kiválasztási feltételek (új tételek):** csak fix áras vagy alkuképes hirdetés, mert az aukciós ár még emelkedhet. "
        f"Legalább 10 hasonló aktív eBay-hirdetés, vagyis van piac. A legkisebb elfogadható ár legfeljebb a piaci medián. "
        "A nettó haszon a medián áron legalább 60% és legalább 40 USD. "
        "A **kezdő hirdetési ár** a hasonló aktív eBay-hirdetések mediánja. Az **eladási idő ezen az áron** a piac mélységétől függ: "
        "30 vagy több aktív hirdetésnél 2–6 hét, 15–29-nél 3–8 hét, 8–14-nél 1–3 hónap. "
        "A **legkisebb elfogadható ár** és a hozzá tartozó likviditás ugyanazzal a szabállyal készült, mint a Herendi/Zsolnay tételeknél (lásd lent, „Módszer”). "
        "A **nettó haszon** a kezdő áron számolt eladási ár a piactéri díj levonása után, mínusz a Vatera-ár. A szállítást a vevő fizeti, a vámot és a Vaterán belüli postaköltséget nem vontam le. "
        "Csöveknél, ha a hirdetés több darabot tartalmaz, az eBay-összehasonlítás darabárra készült.")
    add("")
    add(f"*Kiszűrve:* {st['nincs_modell']} hirdetésnél nem volt felismerhető modell, {st['nincs_eleg_comps']}-nél kevés az eBay-összehasonlító hirdetés, "
        f"{st['floor_median_felett']}-nél a fedezet a piaci medián felett van, {st['kicsi_arres']}-nél kicsi az árrés, és {st['nem_fix']} aukciós vagy ár nélküli.")
    add("")
    add("| Tétel | Kategória | Vatera ár | Kezdő hirdetési ár · piactér | Becsült eladási idő ezen az áron | Likviditás ezen az áron "
        "| Legkisebb elfogadható ár | Eladási idő és likviditás a legkisebb áron | Becsült nettó haszon a kezdő áron "
        "| Aktív eBay-kínálat (db, medián, alsó–felső negyed) | Értékelés |")
    add("|---|---|---:|---:|---|---|---:|---|---:|---|---|")
    for row in table:
        add("| " + " | ".join(row["cells"]) + " |")
    add("")
    add("**Fontos:** a Vatera-hirdetések fotóit és állapotleírását vásárlás előtt egyenként ellenőrizd. Objektíveknél a lencse "
        "tisztasága (gomba, pára, karc), óráknál a működés és az eredeti alkatrészek, csöveknél a mért érték határozza meg a tényleges árat. "
        "A likviditás az aktív kínálatból becsült érték, lezárt eBay-eladásokat nem lehetett lekérni. "
        "Az öt Poljot Chronograph ugyanattól az eladótól, „NOS” (új, használatlan) megjelöléssel szerepel: vásárlás előtt kérj fotót a szerkezetről és a hátlapról, mert sok felújított vagy vegyes alkatrészű példány van forgalomban, ezek jóval kevesebbet érnek. "
        "A 100 USD alatti tételeknél (Zenit, Tungsram csövek) az USA-ba küldés költsége a vevő szemében drágítja a tételt: ezeket érdemes eBay.de-n, EU-n belül, vagy több darabot egy csomagban eladni.")
    add("")

add("## Claude válogatás")
add("")
if picks.get("modszer"):
    add(picks["modszer"])
    add("")
add(f"Összesen **{len(sel)}** javaslat, eladási típus szerint szétválasztva.")
add("")
for t, lbl, fname in TYPES:
    group = [p for p in sel if by_id[p["listing_id"]]["sale_type"] == t]
    if not group:
        continue
    add(f"### {lbl} ({len(group)} tétel)")
    add("")
    for p in group:
        r = by_id[p["listing_id"]]
        add(f"#### [{cell(r['title'])}]({r['url']})")
        add("")
        extra = ""
        if t == "aukcio":
            extra = f" ({r['price_kind']}"
            extra += f", {r['bid_count']} licit" if r["bid_count"] else ""
            extra += f", vége: {r['end_time']}" if r["end_time"] else ""
            extra += ")"
        add(f"- **{KAT_LABEL[p['kategoria']]}** · bizalom: **{p['bizalom']}** · {r['brand']}")
        add(f"- Ár: **{huf(r['price_huf'])}**{extra} · becsült nyugati ár: "
            f"**{p['becsult_ertek_eur_min']}–{p['becsult_ertek_eur_max']} EUR**")
        if r["damage_flags"]:
            add(f"- Állapot jelzők a hirdetésben: {r['damage_flags']}")
        add(f"- Indoklás: {p['indoklas']}")
        add(f"- Kockázat: {p['kockazatok']}")
        add(f"- Link: <{r['url']}>")
        add("")
placement_path = Path(sys.argv[4]) if len(sys.argv) > 4 else None
if placement_path:
    # régi (piacterek, miért ott) + új (kutatás: likviditás, idő, értékelés) adatok
    pl = json.loads(placement_path.read_text(encoding="utf-8"))
    pl2 = json.loads((placement_path.parent / "placement2.json").read_text(encoding="utf-8"))
    liq = json.loads((placement_path.parent / "liquidity.json").read_text(encoding="utf-8"))
    fix_picks = [p for p in sel if by_id[p["listing_id"]]["sale_type"] == "fix"]
    missing_pl = [p["listing_id"] for p in fix_picks
                  if p["listing_id"] not in pl2["tetelek"] or p["listing_id"] not in liq]
    if missing_pl:
        raise SystemExit(f"Hiányzó piactér-javaslat: {missing_pl}")

    def money(v, c):
        s = f"{int(v):,}".replace(",", " ")
        return f"{s} USD" if c == "USD" else f"{s} EUR"

    add("## Hol, mennyiért és milyen gyorsan adhatók el a fix áras tételek")
    add("")
    add(pl2["bevezeto"])
    add("")
    add("### Módszer")
    add("")
    for line in pl2["modszer"]:
        add(f"- {line}")
    add("")
    add(pl2["ertekeles_leiras"])
    add("")
    add("### A javasolt piacterek")
    add("")
    for name, text in pl["piacterek"]:
        add(f"- **{name}:** {text}")
    add("")
    counts = {}
    for p in fix_picks:
        v = pl2["tetelek"][p["listing_id"]]["ertekeles"]
        counts[v] = counts.get(v, 0) + 1
    add("**Összesítés:** " + " · ".join(f"{k}: {counts.get(k, 0)} tétel"
                                         for k in ("Ajánlott", "Szűk árrés", "Nem ajánlott")))
    add("")
    for platform in ("eBay.com", "eBay.de", "Etsy", "Catawiki"):
        group = [p for p in fix_picks if liq[p["listing_id"]]["platform"] == platform]
        if not group:
            continue
        order = {"Ajánlott": 0, "Szűk árrés": 1, "Nem ajánlott": 2}
        group.sort(key=lambda p: order[pl2["tetelek"][p["listing_id"]]["ertekeles"]])
        ask_label = "Kért becsérték" if platform == "Catawiki" else "Kezdő hirdetési ár"
        floor_label = "Minimálár" if platform == "Catawiki" else "Legkisebb elfogadható ár"
        add(f"### {platform} ({len(group)} tétel)")
        add("")
        add(f"| Tétel | Vatera ár | {ask_label} | Becsült eladási idő ezen az áron | Likviditás ezen az áron "
            f"| {floor_label} | Eladási idő és likviditás a legkisebb áron | Aktív eBay-kínálat (db, medián, alsó–felső negyed) "
            f"| Értékelés | Megjegyzés |")
        add("|---|---:|---:|---|---|---:|---|---|---|---|")
        for p in group:
            lid = p["listing_id"]
            r, lq, T = by_id[lid], liq[lid], pl2["tetelek"][lid]
            add(f"| [{cell(r['title'])}]({r['url']}) | {huf(r['price_huf'])} (≈ {money(lq['koltseg'], lq['cur'])}) "
                f"| {money(lq['ask'], lq['cur'])} | {T['ask_ido']} | {T['ask_liq']} "
                f"| {money(lq['floor'], lq['cur'])} | {T['floor_ido']}, {T['floor_liq']} | {lq['comps_txt']} "
                f"| **{T['ertekeles']}** | {cell(T['megj'])} |")
        add("")
    add(pl["megjegyzes"])
    add("")
    add("### Források")
    add("")
    for title, url in pl2["forrasok"]:
        add(f"- [{title}]({url})")
    add("")

if picks.get("korlatok"):
    add("## Adatminőségi korlátok")
    add("")
    for item in picks["korlatok"]:
        add(f"- {item}")
    add("")
add("---")
add("")
add("A becsült nyugati árak szakértői becslések, nem valós idejű piaci adatok. Nagy értékű "
    "vásárlás előtt érdemes eBay „sold” listákkal és a hirdetés fotóival (jelzés, sérülés) ellenőrizni.")
write("README.md", L)

# Típusonkénti fájlok ------------------------------------------------------------
for t, lbl, fname in TYPES:
    group = [r for r in rows if r["sale_type"] == t]
    if not group:
        continue
    group.sort(key=lambda r: (r["brand"], -int(r["price_huf"] or 0)))
    L = [f"# {lbl} – {len(group)} hirdetés", "",
         f"Készült: {STAMP}. Márka, majd ár szerint csökkenő sorrendben. "
         "★ = szerepel a [README](README.md) válogatásában. "
         "Jelölések: *minta* = felismert dekor, *sérülés* = sérülésre utaló szó, "
         "*gyanú* = pl. „mintás”, „jelzetlen”.", ""]
    for brand in sorted({r["brand"] for r in group}):
        sub = [r for r in group if r["brand"] == brand]
        L += [f"## {brand} ({len(sub)} db)", ""]
        if t == "aukcio":
            L += ["| Hirdetés | Ár | Ár típusa | Licit | Vége | Jelölések | Link |",
                  "|---|---:|---|---:|---|---|---|"]
        else:
            L += ["| Hirdetés | Ár | Jelölések | Link |", "|---|---:|---|---|"]
        for r in sub:
            star = "★ " if r["listing_id"] in picked else ""
            title = f"{star}[{cell(r['title'])}]({r['url']})"
            if t == "aukcio":
                L.append(f"| {title} | {huf(r['price_huf'])} | {r['price_kind']} | "
                         f"{r['bid_count'] or ''} | {cell(r['end_time'])} | {cell(flags(r))} | {r['url']} |")
            else:
                L.append(f"| {title} | {huf(r['price_huf'])} | {cell(flags(r))} | {r['url']} |")
        L.append("")
    write(fname, L)

# Kiszűrtek ----------------------------------------------------------------------
L = [f"# Kiszűrt hirdetések – {len(rejected)} db", "",
     "Utánzat-gyanú, nem porcelán tétel vagy hiányzó márkanév miatt kimaradtak. Érdemes átnézni.", ""]
if rejected:
    L += ["| Hirdetés | Ár | Kiszűrés oka | Link |", "|---|---:|---|---|"]
    for r in sorted(rejected, key=lambda r: r["reject_reason"]):
        L.append(f"| [{cell(r['title'])}]({r['url']}) | {huf(r['price_huf'])} | "
                 f"{cell(r['reject_reason'])} | {r['url']} |")
write("kiszurt.md", L)

print(f"{out_dir}: {len(sel)} javaslat, {len(rows)} hirdetés "
      f"({dict(types)}), {len(rejected)} kiszűrt")
