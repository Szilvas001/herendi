"""Általános gyűjtő a schema.org Product adatot közlő oldalakhoz.

Sok piactér és aukciós oldal kiteszi a termékoldalra a schema.org `Product`
JSON-LD blokkot: név, leírás, képek listája és az `offers` ár. Ahol ez megvan,
ott forrásonként nem kell külön elemzőt írni, elég egy konfigurációs bejegyzés.

Felderítés: a forrás saját sitemapje (a robots.txt hirdeti meg). A tétel URL-je
tartalmazza a címet, így a márkaszűrés már a sitemap szintjén megtörténik, és
csak a valóban érdekes termékoldalak töltődnek le.

Kimenet: a `pg.beir` által várt adatpont. Csak az kerül tovább, aminek legalább
három képe, érdemi leírása és ára van.
"""
from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from .. import settings, text as szoveg
from .base import to_int_huf

log = logging.getLogger(__name__)

_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.I)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# schema.org availability -> a mi státuszaink
ELERHETOSEG = {
    "instock": "active", "in_stock": "active", "preorder": "active",
    "outofstock": "ended", "out_of_stock": "ended", "sold": "sold",
    "soldout": "sold", "discontinued": "ended",
}


def _jsonld_csomopontok(soup: BeautifulSoup) -> list[dict]:
    ki: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            adat = json.loads(tag.string or tag.get_text() or "{}")
        except (ValueError, TypeError):
            continue
        halom = adat if isinstance(adat, list) else [adat]
        while halom:
            n = halom.pop()
            if not isinstance(n, dict):
                continue
            ki.append(n)
            if isinstance(n.get("@graph"), list):
                halom.extend(n["@graph"])
    return ki


def _tipus(n: dict) -> set[str]:
    t = n.get("@type")
    if isinstance(t, str):
        return {t.lower()}
    if isinstance(t, list):
        return {str(x).lower() for x in t}
    return set()


def _elso_ajanlat(termek: dict) -> dict:
    aj = termek.get("offers")
    if isinstance(aj, list):
        return next((a for a in aj if isinstance(a, dict)), {})
    return aj if isinstance(aj, dict) else {}


def _kepek(termek: dict) -> list[str]:
    nyers = termek.get("image")
    ki = []
    for u in (nyers if isinstance(nyers, list) else [nyers]):
        if isinstance(u, dict):
            u = u.get("url") or u.get("contentUrl")
        if isinstance(u, str) and u.strip():
            ki.append(u.strip())
    # sorrendtartó duplikátumszűrés
    latott, egyedi = set(), []
    for u in ki:
        if u not in latott:
            latott.add(u)
            egyedi.append(u)
    return egyedi


def _morzsa_kategoria(csomopontok: list[dict]) -> str | None:
    for n in csomopontok:
        if "breadcrumblist" in _tipus(n):
            nevek = []
            for e in n.get("itemListElement") or []:
                if isinstance(e, dict):
                    tetel = e.get("item")
                    nev = (tetel.get("name") if isinstance(tetel, dict) else None) or e.get("name")
                    if nev:
                        nevek.append(str(nev))
            if nevek:
                return " > ".join(nevek)
    return None


def _tiszta_szoveg(ertek) -> str:
    if not isinstance(ertek, str):
        return ""
    return re.sub(r"\s+", " ", _HTML_TAG_RE.sub(" ", ertek)).strip()


class SchemaOrgForras:
    """Egy konfigurációval leírt forrás: sitemap + schema.org Product."""

    def __init__(self, nev: str, cfg: dict | None = None, corpus: str = "relevant"):
        """corpus: "relevant" = csak Herendi/Zsolnay, "general" = teljes
        porcelán/kerámia korpusz az előtanításhoz."""
        self.nev = nev
        self.cfg = cfg if cfg is not None else (settings.get(f"harvest.{nev}") or {})
        if not self.cfg:
            raise ValueError(f"nincs [harvest.{nev}] beállítás")
        if corpus not in ("relevant", "general"):
            raise ValueError("corpus: relevant | general")
        self.corpus = corpus
        self.market = self.cfg.get("market", "HU")
        kulcs = "slug_patterns" if corpus == "relevant" else "slug_patterns_general"
        minta = self.cfg.get(kulcs) or self.cfg.get("slug_patterns") or []
        self._slug = re.compile("|".join(minta), re.I) if minta else None
        self._tetel = re.compile(self.cfg["item_url_pattern"]) if self.cfg.get("item_url_pattern") else None

    # -- felderítés ----------------------------------------------------------
    def sitemap_gyoker(self) -> str:
        return self.cfg["sitemap_url"]

    @staticmethod
    def _locok(tartalom: str) -> list[str]:
        """URL-ek egy sitemapból. A sitemaps.org szerint a sitemap lehet XML vagy
        soronként egy URL-t tartalmazó szöveges fájl; több nagy oldal az utóbbit
        használja, ezért mindkettőt olvassuk."""
        if "<loc" in (tartalom or ""):
            return _LOC_RE.findall(tartalom)
        return [sor.strip() for sor in (tartalom or "").splitlines()
                if sor.strip().startswith(("http://", "https://"))]

    def sitemap_alatt(self, url: str, xml: str) -> tuple[list[str], list[str]]:
        """(al-sitemapek, tétel-URL-ek) egy sitemap tartalmából."""
        alsitemapek, tetelek = [], []
        for loc in self._locok(xml):
            if loc == url:
                continue
            utvonal = urlparse(loc).path
            if self._tetel and self._tetel.search(utvonal):
                if self._slug and not self._slug.search(loc):
                    continue
                tetelek.append(loc.split("#")[0])
            elif "sitemap" in utvonal.lower() or loc.endswith((".xml", ".xml.gz")):
                alsitemapek.append(loc)
        return alsitemapek, tetelek

    # -- termékoldal ---------------------------------------------------------
    def adatpont(self, url: str, html: str) -> dict | None:
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        csomopontok = _jsonld_csomopontok(soup)
        termek = next((n for n in csomopontok if "product" in _tipus(n)), None)
        if termek is None:
            return None

        kepek = _kepek(termek)
        leiras = _tiszta_szoveg(termek.get("description"))
        ajanlat = _elso_ajanlat(termek)
        penznem = (ajanlat.get("priceCurrency") or "HUF").upper()
        nyers_ar = ajanlat.get("price") or ajanlat.get("lowPrice") or ajanlat.get("highPrice")
        ar = to_int_huf(str(nyers_ar)) if nyers_ar is not None else None
        if ar and penznem != "HUF":
            arfolyam = settings.get(f"fx.huf_per_{penznem.lower()}")
            ar = int(ar * arfolyam) if arfolyam else None

        cim = (termek.get("name") or "").strip()
        elerheto = str(ajanlat.get("availability") or "").rsplit("/", 1)[-1].lower()
        allapot = ELERHETOSEG.get(elerheto, "active")
        jellemzok = szoveg.extract(cim, leiras, _morzsa_kategoria(csomopontok) or "")
        relevancia, indok = szoveg.relevance(cim, jellemzok)

        return {
            "source": self.nev,
            "source_id": str(termek.get("sku") or termek.get("productID")
                             or urlparse(url).path.strip("/").rsplit("/", 1)[-1]),
            "url": url,
            "market": self.market,
            "title": cim,
            "description": leiras,
            "category": _morzsa_kategoria(csomopontok),
            "price_huf": ar,
            "price_type": "realized_sale" if allapot == "sold" else "asking_active",
            "price_amount": float(nyers_ar) if nyers_ar not in (None, "") else None,
            "currency": penznem,
            "sale_type": "fix",
            "end_time": None,
            "brand": jellemzok.get("brand"),
            "object_type": jellemzok.get("object_type"),
            "decor": jellemzok.get("decor"),
            "size_cm": jellemzok.get("size_cm"),
            "pieces": jellemzok.get("pieces"),
            "condition": jellemzok.get("condition"),
            "relevance": relevancia,
            "corpus": "herend_zsolnay" if jellemzok.get("brand") else "general",
            "observed_at": None,        # a betöltő tölti ki
            "images": [{"url": u} for u in kepek],
            "raw": {"availability": elerheto, "status": allapot, "relevance": relevancia,
                    "reject_reason": indok, "seller_label": ajanlat.get("seller"),
                    "item_condition": ajanlat.get("itemCondition")},
        }
