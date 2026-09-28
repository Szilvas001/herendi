"""Tényleg blokkol-e a forrás, vagy csak a captcha-szkript szerepel az oldalon.

A crawler blokkolásjelzője a teljes HTML-ben keres mintákat, ezért egy oldal,
amely csak a bejelentkezéshez tölt captchát, tévesen blokkoltnak látszhat. Itt a
nyers HTTP-státuszt, a WAF-fejlécet és a tényleges tartalom méretét nézzük.
"""
from __future__ import annotations

import re

import requests

from porcelan import settings

UA = settings.get("http")["user_agent"]

OLDALAK = [
    "https://www.darabanth.hu/hu/",
    "https://axioart.com/",
    "https://www.jofogas.hu/magyarorszag?q=herendi",
    "https://www.muzeumantikvarium.hu/",
    "https://www.galeriasavaria.hu/",
    "https://bav.hu/",
]


def nez(url: str) -> None:
    try:
        r = requests.get(url, timeout=25, headers={"User-Agent": UA,
                                                   "Accept-Language": "hu-HU,hu;q=0.9"})
    except requests.RequestException as exc:
        print(f"{url:50} HÁLÓZATI HIBA {type(exc).__name__}")
        return
    szoveg = r.text or ""
    waf = r.headers.get("x-amzn-waf-action") or r.headers.get("cf-mitigated") or ""
    szerver = r.headers.get("server", "")
    # valódi tartalom jele: sok látható szöveg és hivatkozás
    linkek = len(re.findall(r"<a\s+[^>]*href=", szoveg, re.I))
    cim = re.search(r"<title[^>]*>(.*?)</title>", szoveg, re.I | re.S)
    jelzok = [m for m in ("cf-chl", "challenge-platform", "turnstile", "hcaptcha",
                          "g-recaptcha", "captcha") if m in szoveg.lower()]
    print(f"{url:50} HTTP {r.status_code} | {len(szoveg):>7} b | {linkek:>4} link | "
          f"server={szerver[:12]:12} waf={waf[:10]:10} jelzők={','.join(jelzok) or '-'}")
    if cim:
        print(f"{'':50} cím: {cim.group(1).strip()[:90]}")


if __name__ == "__main__":
    for u in OLDALAK:
        nez(u)
