"""Darabanth aukciósház: realizált (leütési) árak saját elemzővel.

Az oldal nem közöl schema.org Product JSON-LD blokkot, hanem microdata-t és
egyszerű szöveges mezőket ("Leírás:", "Eladási ár:", "Kikiáltási ár:"). Ezért
kap saját elemzőt, de a felderítés és a kimenet formája ugyanaz, mint az
általános schema.org-gyűjtőé.

Ami itt értékes: az "Eladási ár" egy lezárult aukció tényleges leütési ára,
vagyis realizált ár. Ebből van a legkevesebb, és ez kell az árbecslő
kalibrálásához.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .. import text as szoveg
from .base import to_int_huf
from .schemaorg import SchemaOrgForras, _tiszta_szoveg

log = logging.getLogger(__name__)

# A tétel képei: .../images/3/6/3641147.jpg és a betűvel jelölt további nézetek
# (3641147a.jpg, ...b, ...c). A images_thumbs/ ugyanazok kicsiben, azt kihagyjuk.
_KEP_RE = re.compile(r"https?://static\.darabanth\.com/images/[\w/]+/(\d+[a-z]?)\.jpe?g", re.I)
_ELADASI_RE = re.compile(r"Eladási\s*ár\s*:?\s*([\d\s.\u00a0]+)\s*Ft", re.I)
_KIKIALTASI_RE = re.compile(r"Kikiáltási\s*ár\s*:?\s*([\d\s.\u00a0]+)\s*Ft", re.I)
_LEIRAS_RE = re.compile(r"Leírás:\s*(.+?)(?:\s{2,}|Kategória:|Tétel:|Aukció:|$)", re.S)
_TETELSZAM_RE = re.compile(r"/(\d{5,})(?:[/?]|$)")


class DarabanthForras(SchemaOrgForras):
    """A felderítést az ősétől örökli, a termékoldalt maga elemzi."""

    def adatpont(self, url: str, html: str) -> dict | None:
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")

        cim = ""
        nev_tag = soup.find(attrs={"itemprop": "name"})
        if nev_tag is not None:
            cim = (nev_tag.get("content") or nev_tag.get_text(" ", strip=True) or "")
        cim = re.sub(r"\s*\|\s*Darabanth.*$", "", cim).strip()
        if not cim:
            cim_tag = soup.find("title")
            cim = re.sub(r"\s*\|\s*Darabanth.*$", "", cim_tag.get_text() if cim_tag else "").strip()
        if not cim:
            return None

        # Képek: a teljes méretű nézetek, azonosító szerint sorrendben, egyszer.
        kepek, latott = [], set()
        for m in _KEP_RE.finditer(html):
            teljes = m.group(0)
            if "images_thumbs" in teljes:
                continue
            if m.group(1) not in latott:
                latott.add(m.group(1))
                kepek.append(urljoin(url, teljes))
        kepek.sort()

        for tag in soup.find_all(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        szovegtorzs = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

        m = _LEIRAS_RE.search(szovegtorzs)
        leiras = _tiszta_szoveg(m.group(1)) if m else ""
        if len(leiras) < 20:
            leiras = cim          # a Darabanthnál a cím maga a tételleírás

        eladasi = _ELADASI_RE.search(szovegtorzs)
        kikialtasi = _KIKIALTASI_RE.search(szovegtorzs)
        if eladasi:
            ar, artipus = to_int_huf(eladasi.group(1)), "auction_final_bid"
        elif kikialtasi:
            ar, artipus = to_int_huf(kikialtasi.group(1)), "auction_start_price"
        else:
            ar, artipus = None, "ismeretlen"

        azonosito = None
        for m in _TETELSZAM_RE.finditer(urlparse(url).path):
            azonosito = m.group(1)
        if not azonosito and kepek:
            azonosito = re.sub(r"\D", "", kepek[0].rsplit("/", 1)[-1])

        jellemzok = szoveg.extract(cim, leiras, "")
        relevancia, _ = szoveg.relevance(cim, jellemzok)

        return {
            "source": self.nev,
            "source_id": str(azonosito or urlparse(url).path.strip("/").rsplit("/", 1)[-1])[:100],
            "url": url,
            "market": self.market,
            "title": cim[:300],
            "description": leiras[:4000],
            "category": None,
            "price_huf": ar,
            "price_type": artipus,
            "price_amount": float(ar) if ar else None,
            "currency": "HUF",
            "sale_type": "aukcio",
            "end_time": None,
            "brand": jellemzok.get("brand"),
            "object_type": jellemzok.get("object_type"),
            "decor": jellemzok.get("decor"),
            "size_cm": jellemzok.get("size_cm"),
            "pieces": jellemzok.get("pieces"),
            "condition": jellemzok.get("condition"),
            "relevance": relevancia,
            "corpus": "herend_zsolnay" if jellemzok.get("brand") else "general",
            "observed_at": None,
            "images": [{"url": u} for u in kepek],
            "raw": {"ar_alapja": "Eladási ár" if eladasi else ("Kikiáltási ár" if kikialtasi else None)},
        }
