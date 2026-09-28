"""Mely források engedik a bejárást: robots.txt ellenőrzés a bővítés előtt.

Minden jelölt forrásnál megnézzük, hogy a saját User-Agentünkkel bejárható-e a
keresési/listaoldal és egy termékoldal-minta. Ahol tilos, oda nem megyünk.
"""
from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse

import requests

from porcelan import settings

UA = settings.get("http")["user_agent"]

JELOLTEK = {
    "jofogas.hu": ["https://www.jofogas.hu/magyarorszag?q=herendi",
                   "https://www.jofogas.hu/budapest/herendi-porcelan-123456789.htm"],
    "darabanth.hu": ["https://www.darabanth.hu/hu/online-aukcio/",
                     "https://www.darabanth.hu/hu/online-aukcio/123456/"],
    "axioart.com": ["https://axioart.com/kereses?q=herendi",
                    "https://axioart.com/tetel/123456"],
    "muzeumantikvarium.hu": ["https://www.muzeumantikvarium.hu/", ],
    "bav.hu": ["https://bav.hu/", "https://bav.hu/aukcio/"],
    "galeriasavaria.hu": ["https://www.galeriasavaria.hu/kereses/?q=herendi",
                          "https://www.galeriasavaria.hu/termekek/reszletek/123456/"],
    "vatera.hu": ["https://www.vatera.hu/antik-regiseg/porcelanok/index-c212.html",
                  "https://www.vatera.hu/listings/index.php?q=herendi"],
}


def vizsgal(host: str, urlek: list[str]) -> None:
    gyoker = f"https://{host}"
    rp = urllib.robotparser.RobotFileParser()
    try:
        r = requests.get(gyoker + "/robots.txt", timeout=20, headers={"User-Agent": UA})
    except requests.RequestException as exc:
        print(f"{host:24} robots.txt nem érhető el: {type(exc).__name__}")
        return
    if r.status_code != 200:
        print(f"{host:24} nincs robots.txt (HTTP {r.status_code}) -> nincs tiltás")
        rp = None
    else:
        rp.parse(r.text.splitlines())

    for u in urlek:
        ok = True if rp is None else rp.can_fetch(UA, u)
        print(f"{host:24} {'ENGEDI ' if ok else 'TILTJA '} {urlparse(u).path[:60] or '/'}"
              f"{('?' + urlparse(u).query[:30]) if urlparse(u).query else ''}")
    if rp is not None:
        kesleltetes = rp.crawl_delay(UA)
        if kesleltetes:
            print(f"{host:24} crawl-delay: {kesleltetes} mp")


if __name__ == "__main__":
    for host, urlek in JELOLTEK.items():
        vizsgal(host, urlek)
        print()
