"""Egy forrás alkalmassága a kép-ár korpuszhoz, egy futással eldöntve.

Amit megnéz, ebben a sorrendben:
  1. robots.txt engedi-e a tétel- és listaoldalakat,
  2. van-e sitemap, és abban hány márkás tétel található,
  3. a termékoldal ad-e schema.org Product adatot,
  4. a mintatételeken teljesül-e a három kép + leírás + ár feltétel.

Használat:  python forras_kiertekeles.py <nev> [<nev> ...]
            python forras_kiertekeles.py --mind
"""
from __future__ import annotations

import json
import re
import sys
import urllib.robotparser

import requests

from porcelan import settings
from porcelan.net import BlockedError, Fetcher
from porcelan.sources.schemaorg import SchemaOrgForras

UA = settings.get("http")["user_agent"]
MARKA = re.compile(r"herend|zsolnay|eozin|eosin|pirogranit", re.I)

JELOLTEK: dict[str, dict] = {
    # --- magyar használt piac ---
    "darabanth": {
        "base": "https://www.darabanth.hu",
        "sitemap_url": "https://www.darabanth.hu/sitemap.xml",
        "item_url_pattern": r"/(hu/)?(online-aukcio|tetel|item)/",
        "market": "HU",
    },
    "bav": {
        "base": "https://bav.hu",
        "sitemap_url": "https://bav.hu/xmlsitemap",
        "item_url_pattern": r"/(termek|aukcio|tetel|arveres)/",
        "market": "HU",
    },
    "muzeumantikvarium": {
        "base": "https://www.muzeumantikvarium.hu",
        "sitemap_url": "https://www.muzeumantikvarium.hu/sitemap.xml",
        "item_url_pattern": r"/(termek|tetel|item|konyv)/",
        "market": "HU",
    },
    "galeriasavaria": {
        "base": "https://galeriasavaria.hu",
        "sitemap_url": "https://galeriasavaria.hu/sitemap/sitemap.xml",
        "item_url_pattern": r"/termekek/reszletek/",
        "market": "HU",
    },
    # --- nyugati piac (az üzleti koncepció eladási oldala) ---
    "replacements": {
        "base": "https://www.replacements.com",
        "sitemap_url": "https://www.replacements.com/sitemap.xml",
        "item_url_pattern": r"/(china|crystal|silver)/",
        "market": "US",
    },
    "rubylane": {
        "base": "https://www.rubylane.com",
        "sitemap_url": "https://www.rubylane.com/sitemap.xml",
        "item_url_pattern": r"/item/",
        "market": "US",
    },
    "chairish": {
        "base": "https://www.chairish.com",
        "sitemap_url": "https://www.chairish.com/sitemap.xml",
        "item_url_pattern": r"/product/",
        "market": "US",
    },
    "1stdibs": {
        "base": "https://www.1stdibs.com",
        "sitemap_url": "https://www.1stdibs.com/sitemap.xml",
        "item_url_pattern": r"/(furniture|dining-entertaining|more)/",
        "market": "US",
    },
    "etsy": {
        "base": "https://www.etsy.com",
        "sitemap_url": "https://www.etsy.com/sitemap.xml",
        "item_url_pattern": r"/listing/",
        "market": "US",
    },
    "catawiki": {
        "base": "https://www.catawiki.com",
        "sitemap_url": "https://www.catawiki.com/en/sitemaps/com/en/sitemap_open_index_en.xml",
        "item_url_pattern": r"/l/",
        "market": "EU",
    },
}

MAX_SITEMAP = 12        # ennyi sitemap-fájlt nézünk meg mintaként
MAX_TETEL = 6           # ennyi termékoldalt töltünk le mintaként


def _robots(base: str):
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(base + "/robots.txt", timeout=25, headers={"User-Agent": UA})
    except requests.RequestException as exc:
        return None, f"robots.txt nem érhető el ({type(exc).__name__})"
    if r.status_code != 200:
        return None, f"nincs robots.txt (HTTP {r.status_code})"
    rp.parse(r.text.splitlines())
    sm = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)
    return (rp, sm), None


def kiertekel(nev: str, cfg: dict) -> dict:
    ki = {"forras": nev, "piac": cfg["market"], "alkalmas": False, "ok": None,
          "sitemap_nezett": 0, "marka_tetel_mintaban": 0, "minta_letoltve": 0,
          "schema_product": 0, "megfelel_3kep": 0, "peldak": []}

    robots, hiba = _robots(cfg["base"])
    if hiba:
        ki["robots"] = hiba
        rp, hirdetett = None, []
    else:
        rp, hirdetett = robots
        ki["robots"] = "van"
        ki["robots_sitemap"] = hirdetett[:3]

    proba = cfg["sitemap_url"]
    if rp is not None and not rp.can_fetch(UA, proba):
        ki["ok"] = "a robots.txt tiltja a sitemapet"
        return ki

    f = Fetcher()
    forras = SchemaOrgForras(nev, {**cfg, "slug_patterns": [MARKA.pattern]})

    # 1. sitemap bejárás mintavételesen
    varo = [proba] + [u for u in hirdetett if u != proba]
    latott, tetelek = set(), []
    while varo and ki["sitemap_nezett"] < MAX_SITEMAP and len(tetelek) < 400:
        u = varo.pop(0)
        if u in latott:
            continue
        latott.add(u)
        try:
            r = f.get(u, ttl=3600)
        except BlockedError as exc:
            ki["ok"] = f"bot-ellenőrzés: {str(exc)[:80]}"
            return ki
        except Exception as exc:
            ki.setdefault("sitemap_hibak", []).append(f"{u[-40:]}: {type(exc).__name__}")
            continue
        if r is None or r.status != 200 or not forras._locok(r.text or ""):
            ki.setdefault("sitemap_hibak", []).append(f"{u[-40:]}: HTTP {getattr(r,'status','-')}")
            continue
        ki["sitemap_nezett"] += 1
        alsitemapek, talalt = forras.sitemap_alatt(u, r.text)
        tetelek.extend(talalt)
        varo.extend(alsitemapek[:40])

    ki["marka_tetel_mintaban"] = len(tetelek)
    if not tetelek:
        ki["ok"] = ("nincs sitemap vagy nincs benne felismerhető márkás tétel-URL "
                    "(lehet, hogy más URL-minta kell)")
        return ki

    # 2. mintatételek
    for u in tetelek[:MAX_TETEL]:
        try:
            r = f.get(u, ttl=86400)
        except BlockedError as exc:
            ki["ok"] = f"bot-ellenőrzés a termékoldalon: {str(exc)[:80]}"
            return ki
        except Exception as exc:
            continue
        if r is None or r.status != 200 or not r.text:
            continue
        ki["minta_letoltve"] += 1
        adat = forras.adatpont(u, r.text)
        if adat is None:
            continue
        ki["schema_product"] += 1
        kepek = len(adat["images"])
        megfelel = kepek >= 3 and adat["price_huf"] and len(adat["description"]) >= 20
        ki["megfelel_3kep"] += int(bool(megfelel))
        ki["peldak"].append({"cim": (adat["title"] or "")[:55], "kep": kepek,
                             "ar_huf": adat["price_huf"], "leiras_hossz": len(adat["description"])})

    ki["alkalmas"] = ki["megfelel_3kep"] >= 2
    if not ki["alkalmas"] and ki["ok"] is None:
        if ki["schema_product"] == 0:
            ki["ok"] = "a termékoldal nem közöl schema.org Product adatot"
        else:
            ki["ok"] = "a tételek nem érik el a 3 kép + leírás + ár feltételt"
    return ki


if __name__ == "__main__":
    nevek = list(JELOLTEK) if "--mind" in sys.argv else [a for a in sys.argv[1:] if not a.startswith("-")]
    for nev in nevek or list(JELOLTEK):
        print(json.dumps(kiertekel(nev, JELOLTEK[nev]), ensure_ascii=False), flush=True)
