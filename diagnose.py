#!/usr/bin/env python3
"""Vatera diagnózis: ellenőrzi, hogy a scraper feltevései igazak-e az élő oldalon.

Használat (olyan gépen, ahonnan a Vatera elérhető):

    python diagnose.py                       # alap kereséssel
    python diagnose.py --term "zsolnay eozin" --details 3
    python diagnose.py --url https://www.vatera.hu/valami-123456789.html
    python diagnose.py --save-dir diag_html  # HTML-ek mentése (hibakereséshez)

A végén kiír egy ÖSSZEGZÉST arról, melyik feltevés teljesült, és mit kell
igazítani, ha nem. A `--save-dir`-be mentett HTML-ekből közvetlenül lehet
tesztfixture-t csinálni.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from porcelan import config, parsing, vatera
from porcelan.httpclient import HttpClient

OK, WARN, FAIL = "OK  ", "FIGY", "HIBA"

# Amit a termékoldalon keresünk (a scraper ezekre épít).
DETAIL_MARKERS = {
    "fix_price token": r"\bfix_price\b",
    "bid token": r"\bbid\b",
    "'fix ar' felirat": r"fix ar",
    "'aktualis licit' felirat": r"aktualis licit",
    "'kikialtasi ar' felirat": r"kikialtasi ar",
    "'ajanlatot tehetsz' felirat": r"ajanlatot tehetsz",
    "'iranyar' felirat": r"iranyar",
}


class Fetcher:
    """Élesben nyers requests (kell a státuszkód), offline a HttpClient."""

    def __init__(self, offline_dir: Path | None):
        self.offline = HttpClient(offline_dir=offline_dir) if offline_dir else None
        self.session = requests.Session()

    def get(self, url: str) -> tuple[int | str, str, str]:
        """(státusz, végső URL, HTML)"""
        if self.offline:
            return "offline", url, (self.offline.get(url) or "")
        try:
            resp = self.session.get(url, headers=config.HEADERS,
                                    timeout=config.HTTP_TIMEOUT)
            return resp.status_code, resp.url, resp.text or ""
        except Exception as exc:
            return f"hiba: {exc}", url, ""


def line(status: str, text: str) -> None:
    print(f"  [{status}] {text}")


def check_search(fetcher: Fetcher, term: str, saver) -> tuple[list[str], dict]:
    url = vatera.search_url(term, 1)
    print(f"\n1) TALÁLATI OLDAL – '{term}'\n  {url}")
    status, final_url, html = fetcher.get(url)
    saver("search", html)

    result = {"url": url, "status": status, "final_url": final_url,
              "bytes": len(html), "links": 0}

    if not html:
        line(FAIL, f"nincs válasz (státusz: {status}) – hálózat vagy blokkolás")
        return [], result

    line(OK if status in (200, "offline") else FAIL, f"státusz: {status}, {len(html):,} bájt")
    if final_url.rstrip("/") != url.rstrip("/") and "?" not in final_url:
        line(WARN, f"átirányítás ide: {final_url} – a keresési URL formátum változhatott")

    blocked = HttpClient.looks_blocked(html)
    if blocked:
        line(FAIL, f"anti-bot oldal jött vissza ({blocked}) – lásd az összegzést")
        return [], result

    soup = BeautifulSoup(html, "html.parser")
    css_links = [a.get("href", "") for a in soup.select("a[href]")]
    css_products = [h for h in css_links if re.search(config.PRODUCT_URL_RE, h.split("?")[0])]
    regex_products = re.findall(
        r"https?://(?:www\.|ssl\.)?vatera\.hu/[^\s\"'<>]+-\d{6,}\.html", html)
    links = vatera.extract_product_links(html)
    result["links"] = len(links)

    line(OK if links else FAIL,
         f"termék-link: {len(links)} db (a-tagből: {len(css_products)}, "
         f"nyers HTML-ből: {len(set(regex_products))})")
    if not links:
        line(FAIL, "egy termék-link sem illeszkedik a '-<számok>.html' mintára")
        if "json" in html[:5000].lower() or "__NEXT_DATA__" in html:
            line(WARN, "a lista valószínűleg JavaScriptből renderelődik "
                       "(beágyazott JSON) – ezt a parsert kell hozzáigazítani")
    for sample in links[:3]:
        print(f"       - {sample}")
    return links, result


def check_detail(fetcher: Fetcher, url: str, saver, idx: int) -> dict:
    print(f"\n2.{idx}) TERMÉKOLDAL\n  {url}")
    status, _, html = fetcher.get(url)
    saver(f"detail_{idx}", html)
    if not html:
        line(FAIL, f"nincs válasz (státusz: {status})")
        return {"url": url, "status": status, "ok": False}

    blocked = HttpClient.looks_blocked(html)
    if blocked:
        line(FAIL, f"anti-bot oldal ({blocked})")
        return {"url": url, "status": status, "ok": False, "blocked": blocked}

    text_norm = parsing.norm(BeautifulSoup(html, "html.parser").get_text(" ", strip=True))
    html_norm = parsing.norm(html)
    found = {name: bool(re.search(rx, html_norm if "token" in name else text_norm))
             for name, rx in DETAIL_MARKERS.items()}
    line(OK, "jelek: " + ", ".join(f"{n}={'igen' if v else 'nem'}" for n, v in found.items()))

    rec = parsing.parse_listing(url, html)
    if not rec:
        line(FAIL, "a parser nem tudott rekordot előállítani")
        return {"url": url, "status": status, "ok": False, "markers": found}

    line(OK if rec["sale_type"] != config.SALE_UNKNOWN else FAIL,
         f"eladási típus: {rec['sale_type_label']}")
    line(OK if rec["price_huf"] else WARN,
         f"ár: {rec['price_huf']} Ft (forrás: {rec['price_kind']})")
    line(OK if rec["brand"] else WARN, f"márka: {rec['brand']}")
    line(OK, f"cím: {rec['title'][:90]}")
    if not rec["accepted"]:
        line(WARN, f"kiszűrve: {rec['reject_reason']}")
    if rec["damage_flags"]:
        line(OK, f"sérülés jelzők: {rec['damage_flags']}")

    return {"url": url, "status": status, "ok": True, "markers": found,
            "sale_type": rec["sale_type"], "price_huf": rec["price_huf"],
            "brand": rec["brand"], "title": rec["title"]}


def summarise(search: dict, details: list[dict]) -> None:
    print("\n" + "=" * 68)
    print("ÖSSZEGZÉS")
    print("=" * 68)

    if not search.get("links"):
        print("A találati oldal feldolgozása NEM sikerült.")
        if search.get("status") not in (200, "offline"):
            print(f"  - A szerver {search.get('status')} státusszal válaszolt.")
            print("  - Teendő: próbáld böngészőből; ha ott megy, a User-Agent / "
                  "sebesség a gond (VATERA_DELAY=2, --workers 2).")
        else:
            print("  - Az oldal letöltődött, de nem találtunk termék-linket.")
            print("  - Teendő: küldd el a --save-dir mappát; a link-minta és a "
                  "keresési URL (porcelan/config.py: LISTING_URL, PRODUCT_URL_RE) "
                  "ezekből pontosítható.")
        return

    ok_details = [d for d in details if d.get("ok")]
    print(f"Találati oldal: {search['links']} termék-link – rendben.")
    if not details:
        print("Termékoldalt nem néztünk (--details 0).")
        return
    print(f"Termékoldal: {len(ok_details)}/{len(details)} sikeresen elemezve.")

    typed = [d for d in ok_details if d.get("sale_type") != config.SALE_UNKNOWN]
    priced = [d for d in ok_details if d.get("price_huf")]
    branded = [d for d in ok_details if d.get("brand")]
    print(f"  - eladási típus felismerve: {len(typed)}/{len(ok_details)}")
    print(f"  - ár kinyerve:              {len(priced)}/{len(ok_details)}")
    print(f"  - márka felismerve:         {len(branded)}/{len(ok_details)}")

    if ok_details and len(typed) == len(ok_details) and len(priced) == len(ok_details):
        print("\nA scraper feltevései teljesülnek – a teljes futás mehet:")
        print("  python run.py --limit 30 --no-ai   (majd: python run.py)")
    else:
        print("\nVan mit igazítani. A leggyorsabb út:")
        print("  1) futtasd: python diagnose.py --save-dir diag_html")
        print("  2) küldd el a diag_html mappát (vagy 1-2 HTML-t belőle)")
        print("  3) a feliratok/tokenek alapján a porcelan/parsing.py "
              "kulcsszólistái pontosíthatók – hálózat nélkül is.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vatera scraper diagnózis")
    ap.add_argument("--term", default="herendi porcelan", help="keresőkifejezés")
    ap.add_argument("--url", default=None, help="konkrét hirdetés URL vizsgálata")
    ap.add_argument("--details", type=int, default=2,
                    help="hány termékoldalt nézzen meg a találati listából")
    ap.add_argument("--save-dir", type=Path, default=None,
                    help="a letöltött HTML-ek mentése ebbe a mappába")
    ap.add_argument("--offline-dir", type=Path, default=None,
                    help="teszteléshez: hálózat helyett lementett HTML-ek")
    args = ap.parse_args(argv)

    if args.save_dir:
        args.save_dir.mkdir(parents=True, exist_ok=True)

    def saver(name: str, html: str) -> None:
        if args.save_dir and html:
            (args.save_dir / f"{name}.html").write_text(html, encoding="utf-8")

    print("=" * 68)
    print("  VATERA DIAGNÓZIS")
    print("=" * 68)

    fetcher = Fetcher(args.offline_dir)
    details: list[dict] = []

    if args.url:
        search: dict = {"links": 1, "status": "n/a", "skipped": True}
        details.append(check_detail(fetcher, args.url, saver, 1))
    else:
        links, search = check_search(fetcher, args.term, saver)
        for idx, url in enumerate(links[:max(0, args.details)], 1):
            details.append(check_detail(fetcher, url, saver, idx))

    summarise(search, details)

    if args.save_dir:
        (args.save_dir / "diag_report.json").write_text(
            json.dumps({"search": search, "details": details},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nMentve: {args.save_dir}/ (HTML-ek + diag_report.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
