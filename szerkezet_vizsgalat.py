"""Milyen strukturált adatot ad egy forrás: JSON-LD, OpenGraph, sitemap.

Ez dönti el, hogy egy általános, schema.org-alapú kinyerő elég-e, vagy
oldalanként külön elemző kell.
"""
from __future__ import annotations

import json
import re
import sys

from bs4 import BeautifulSoup

from porcelan.net import Fetcher

OLDALAK = {
    "darabanth": "https://www.darabanth.hu/hu/",
    "axioart": "https://axioart.com/",
    "galeriasavaria": "https://www.galeriasavaria.hu/",
    "muzeumantikvarium": "https://www.muzeumantikvarium.hu/",
    "bav": "https://bav.hu/",
}


def jsonld_tipusok(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    tipusok = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            adat = json.loads(tag.string or tag.get_text() or "{}")
        except (ValueError, TypeError):
            tipusok.append("(hibás JSON)")
            continue
        halom = adat if isinstance(adat, list) else [adat]
        while halom:
            n = halom.pop()
            if isinstance(n, dict):
                t = n.get("@type")
                if t:
                    tipusok.append(t if isinstance(t, str) else "/".join(map(str, t)))
                if isinstance(n.get("@graph"), list):
                    halom.extend(n["@graph"])
    return tipusok


def nez(nev: str, url: str) -> None:
    f = Fetcher()
    try:
        r = f.get(url)
    except Exception as exc:
        print(f"{nev:20} HIBA {type(exc).__name__}: {str(exc)[:70]}")
        return
    html = r.text
    soup = BeautifulSoup(html, "html.parser")
    og = {m.get("property"): (m.get("content") or "")[:40]
          for m in soup.find_all("meta", attrs={"property": True})
          if str(m.get("property")).startswith("og:")}
    print(f"{nev:20} JSON-LD típusok: {sorted(set(jsonld_tipusok(html))) or '-'}")
    print(f"{'':20} OpenGraph: {sorted(og) or '-'}")

    # sitemap?
    try:
        rr = f.get(url.rstrip("/") + "/robots.txt")
        sm = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rr.text or "")
        print(f"{'':20} sitemap: {sm[:3] or '-'}")
    except Exception as exc:
        print(f"{'':20} sitemap: hiba ({type(exc).__name__})")
    print()


if __name__ == "__main__":
    valasztott = sys.argv[1:] or list(OLDALAK)
    for nev in valasztott:
        nez(nev, OLDALAK[nev])
