"""Reproduce the reviewed report from stored evidence, without network or API keys.

PYTHONPATH=. python elemzes/build_decision_report.py riport/decision-evidence.json
"""
import json
import re
import sys
from pathlib import Path
from elemzes.decision_model import Costs, scenario, assessment


def money(value):
    return f"{value:,.0f}".replace(",", " ")


def cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def evaluate(row):
    # Explicit planning assumptions, not current FX quotes or carrier tariffs.
    fx = 395 if row["currency"] == "EUR" else 395 / 1.15
    cost = Costs()
    if "porcelán" in row["category"]:
        cost = Costs(packaging=4000, outbound=10000, testing=0)
    if any(word in row["title"].lower() for word in ("étkészlet", "levesestál", "készlet")):
        cost = Costs(packaging=8000, outbound=30000, testing=0)
    if "Poljot" in row["title"]:
        cost = Costs(testing=20000)
    record = row.get("fresh") or {}
    price = record.get("price_huf")
    if not price:
        return {**row, "status": "Nincs ellenőrzött beszerzési ár", "base": None}
    base = scenario(price, row["old_ask"] * .80 * fx, cost)
    stress = scenario(price, row["old_ask"] * .60 * fx, cost)
    count = re.match(r"(\d+) db", row["old_comps"])
    status = assessment(record.get("availability"), record.get("sale_type"),
                        int(count[1]) if count else 0, base, stress)
    return {**row, "status": status, "base": base, "stress": stress,
            "costs": vars(cost), "scenario_sale": row["old_ask"] * .8,
            "stress_sale": row["old_ask"] * .6}


def build(evidence, destination):
    reviewed = [evaluate(row) for row in evidence["previous_candidates"]]
    reviewed.sort(key=lambda r: (r["base"] is not None,
                                r["base"]["roi_pct"] if r["base"] else -999), reverse=True)
    screen = evidence["screen"]
    rows = screen["candidates"]
    active = [r for r in rows if r.get("record") and r["record"].get("accepted")
              and r["record"].get("availability") == "in_stock"
              and r["record"].get("sale_type") in ("fix", "alku")]
    lines = ["# Vatera – friss döntési riport", "",
        f"Ellenőrzés: {evidence['checked_at']} (UTC).", "",
        "**Bizonyítottan nagy likviditású és nagy nettó árrésű vétel: nincs igazolva.** "
        "A friss Vatera-adatok rendelkezésre állnak, de friss, azonos kivitelű és állapotú "
        "lezárt nyugati eladásokból nem sikerült ellenőrizhető mintát szerezni. "
        "Ez nem bizonyítja, hogy nincs jó vétel; azt jelenti, hogy a szükséges bizonyíték hiányzik.", "",
        "## Mit futtattunk?", "",
        f"{screen['search_terms']} keresőkifejezés első találati oldaláról "
        f"{screen['unique_product_links']} egyedi terméklinket gyűjtöttünk "
        f"({len(screen['failed_search_terms'])} sikertelen keresőkifejezés). "
        f"A keresőkártyákból {screen['recognized_fixed_candidates']} felismerhető, fix áras jelölt maradt; "
        f"{screen['model_groups']} modellcsoport két legolcsóbb jelöltjéből összesen {len(rows)} "
        f"termékoldalt ellenőriztünk részletesen. Ebből {len(active)} felelt meg a parser "
        "elfogadási feltételeinek, rendelkezett készletjelzéssel és rögzített vagy irányárral. "
        "Ez célzott minta, nem a teljes Vatera értékelése. A teljes termékoldal-letöltést "
        "megszakítottuk a célzott ellenőrzés javára; az abból származó részadatokat nem "
        "nevezzük teljes futásnak. Emellett a régi összesített táblázat mind a 22 jelöltjét újraellenőriztük.", "",
        "A futtatott új modell `decision_model.py`: determinisztikus költség- és "
        "stresszszámítás. **Új LLM-modell API-futtatása nem történt**, mert nincs API-kulcs. "
        "A régi árbecsléseket nem nevezzük friss piaci vagy realizált eladási áraknak.", "",
        "## Elsőként ellenőrizendő korábbi jelöltek", "",
        "- **Zsolnay birkózó medvék, 32 500 Ft:** a régi 350 EUR becslésből még a "
        "csökkentett árforgatókönyv is pozitív lehet, de az előző riportban sincs hozzá "
        "összehasonlítható piaci minta. Ugyanilyen Markup Béla figura lezárt eladásai "
        "nélkül nem minősül ajánlott vételnek.",
        "- **Tungsram ECC83 pár, 8 500 Ft:** az eladó csak a fűtőszálat mérte; "
        "csőteszteres mérés, zaj- és mikrofonikusság-ellenőrzés szükséges. "
        "A tesztelt/NOS csövek ára nem vihető át automatikusan erre a párra.",
        "- **Poljot kronográfok, 60 000 Ft:** az eladó szerint működnek, de nincs "
        "szervizinformáció. Az eredetiség és a szerkezet ellenőrzése, valamint a "
        "szerviztartalék után a korábbi 63%-os haszon nem tartható biztos becslésnek.", "",
        "## Költségmodell és korlátai", "",
        "Tervezési feltételezések, nem aktuális díj- vagy árfolyamajánlatok: "
        "395 HUF/EUR; 395/1,15 HUF/USD; 18% összesített piactéri/fizetési/devizaköltség; "
        "10% eladási ár arányos kockázati tartalék. Alap: 2 000 Ft belföldi posta, "
        "2 000 Ft csomagolás, 6 000 Ft külföldi posta, 5 000 Ft ellenőrzés. "
        "Porcelán: 4 000 Ft csomagolás, 10 000 Ft külföldi posta, külön tesztdíj nélkül. "
        "Készlet/levesestál: 8 000 és 30 000 Ft. Poljot: 20 000 Ft ellenőrzési/szerviztartalék. "
        "A postát ebben a konzervatív forgatókönyvben az eladó viseli. Ha a vevő fizeti, "
        "a rá jutó díjakkal együtt újra kell számolni. Adó, munkaidő és tőkeköltség nincs benne; "
        "ezért a szám adózás előtti fedezet, nem végső nettó nyereség.", "",
        "Alapeset: a **korábbi, nem ellenőrzött nyugati árbecslés 80%-a**; stressz: 60%-a. "
        "Ezek érzékenységi forgatókönyvek, nem kalibrált ár-előrejelzések. "
        "ROI = fedezet / (vételár + fix költségek). A vételi plafon a 30% cél-ROI-t "
        "biztosító matematikai felső határ az alapeseti feltételek mellett, nem vételi ajánlás. "
        "Az aktív hirdetésszám nem mér eladási sebességet; minden jelölt likviditása ismeretlen.", "",
        "## A korábbi 22 jelölt újraszámítása", "",
        "ROI szerint rendezve; a pozitív szám sem bizonyítja az elérhető piaci árat.", "",
        "| Termék | Friss Vatera ár (Ft) | Feltételezett eladási ár: alap / stressz | Fedezet: alap / stressz (Ft) | ROI alap | Vételi plafon (Ft) | Döntés |",
        "|---|---:|---:|---:|---:|---:|---|"]
    for r in reviewed:
        if not r["base"]:
            lines.append(f"| [{cell(r['title'])}]({r['url']}) | – | – | – | – | – | {r['status']} |")
            continue
        b,s=r["base"],r["stress"]
        lines.append(f"| [{cell(r['title'])}]({r['url']}) | {money(r['fresh']['price_huf'])} | "
                     f"{money(r['scenario_sale'])} / {money(r['stress_sale'])} {r['currency']} | "
                     f"{money(b['profit_huf'])} / {money(s['profit_huf'])} | {b['roi_pct']}% | "
                     f"{money(b['max_purchase_huf'])} | {r['status']} |")
    lines += ["", "## Új, ellenőrizendő jelöltek a friss keresésből", "",
        "A modellnevek regex-alapú csoportok; kivitel, tartozékok, állapot és eredetiség "
        "külön ellenőrzést igényel. Az alábbi lista modellnév, azon belül ár szerint rendezett "
        "kutatási lista, **nem likviditási vagy nyereségrangsor**. Nyugati eladási bizonyíték "
        "nélkül nem gyártunk hozzá hasznot vagy eladási időt.", "",
        "| Modellcsoport | Termék | Friss ár (Ft) | Ellenőrizendő eladói leírás |",
        "|---|---|---:|---|"]
    for r in sorted(active,key=lambda r:(r["model"],r["record"]["price_huf"] or 0)):
        rec=r["record"]
        lines.append(f"| {cell(r['model'])} | [{cell(rec['title'])}]({r['url']}) | "
                     f"{money(rec['price_huf'] or 0)} | {cell(rec['description'][:180])} |")
    lines += ["", "## Ellenőrizhetőség", "",
        "- [Bemeneti pillanatkép és futási adatok](decision-evidence.json)",
        "- [Hitelesítés, kérésfolyam, kulcsok és tokenek](../AUTHENTICATION.md)",
        "- [Előző riport – archivált, nem aktuális ajánlás](korabbi-2026-09-17.md)",
        "- [Új modell](../elemzes/decision_model.py) · [riport újragenerálása](../elemzes/build_decision_report.py)", "",
        "A PicClick friss lekérése HTTP 502-vel sikertelen volt. A nyilvános eBay-keresés "
        "aktív hirdetéseket adott, de nem ellenőrzött, időablakhoz kötött lezárt eladási mintát. "
        "Az eBay [Tungsram kínálata](https://www.ebay.com/b/Tungsram-12ax7/64627/bn_7023391671) "
        "csak aktív ár- és állapotellenőrzésre használható, likviditás igazolására nem.", ""]
    Path(destination).write_text("\n".join(lines),encoding="utf-8")
    print(f"Report: {len(reviewed)} re-evaluated; {len(active)} active research candidates; 0 verified high-liquidity buys")


if __name__ == "__main__":
    source=Path(sys.argv[1])
    build(json.loads(source.read_text()),source.parent / "README.md")
