"""Jófogás adapter (másodlagos forrás; settings: jofogas.enabled).

A Jófogás apróhirdetés: nincs aukció, az ár kért ár (sale_type = 'alku', mert
jellemzően alkuképes). A találati oldal a schema.org JSON-LD `ItemList`-et és a
kártyák linkjeit használja; a HTML-szerkezetet élesben ebből a környezetből nem
lehetett ellenőrizni, ezért a parser tűrő, és `diagnose`-zal ellenőrizendő.
"""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from .. import settings
from .base import Card, IndexPage, Source, Task, to_int_huf

_ID_RE = re.compile(r"_(\d{6,})\.htm")


class JofogasSource(Source):
    name = "jofogas"
    market = "HU"

    def __init__(self):
        self.cfg = settings.get("jofogas")
        self.base = self.cfg["base_url"].rstrip("/")

    def search_url(self, query: str, page: int = 1) -> str:
        params = {"q": query}
        if page > 1:
            params["o"] = page
        return f"{self.base}{self.cfg['search_path']}?{urlencode(params)}"

    def seed_tasks(self, full_catalog: bool = False) -> list[Task]:
        return [Task("search", self.search_url(q), f"query:{q}", 1, 15) for q in self.cfg["queries"]]

    def page_task(self, task: Task, page: int) -> Task:
        p = urlparse(task.url)
        qs = {k: v[0] for k, v in parse_qs(p.query).items()}
        qs["o"] = str(page)
        return Task(task.kind, urlunparse(p._replace(query=urlencode(qs))), task.query, page, task.priority)

    def parse_index(self, url: str, html: str) -> IndexPage:
        soup = BeautifulSoup(html or "", "html.parser")
        cards: dict[str, Card] = {}
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(tag.string or "{}")
            except (ValueError, TypeError):
                continue
            for node in (data if isinstance(data, list) else [data]):
                if isinstance(node, dict) and node.get("@type") == "ItemList":
                    for el in node.get("itemListElement", []):
                        item = el.get("item", el) if isinstance(el, dict) else {}
                        link = item.get("url") or el.get("url")
                        m = _ID_RE.search(link or "")
                        if not m:
                            continue
                        offer = item.get("offers") or {}
                        cards[m.group(1)] = Card(m.group(1), link, item.get("name") or "",
                                                 to_int_huf(offer.get("price")), "alku",
                                                 image_url=item.get("image") if isinstance(item.get("image"), str) else None)
        for a in soup.select("a[href]"):
            href = urljoin(self.base, a["href"]).split("?")[0]
            m = _ID_RE.search(href)
            if not m or m.group(1) in cards:
                continue
            box = a.find_parent(["div", "article", "li"]) or a
            price_el = box.select_one(".price-value, [class*=price]")
            img = box.select_one("img")
            cards[m.group(1)] = Card(m.group(1), href, (a.get("title") or a.get_text(" ", strip=True)),
                                     to_int_huf(price_el.get_text(" ", strip=True)) if price_el else None,
                                     "alku", image_url=(img.get("data-src") or img.get("src")) if img else None)
        total = None
        m = re.search(r"(\d[\d\s.]*)\s*(?:db\s+)?(?:hirdetés|találat)", soup.get_text(" ", strip=True))
        if m:
            total = int(re.sub(r"\D", "", m.group(1)) or 0) or None
        has_next = True if soup.select_one("a[rel=next], .ad-list-pager-item-next, a.jofogasicon-right") else None
        return IndexPage(list(cards.values()), total, has_next, [])

    def is_relevant_card(self, card: Card) -> bool:
        from ..text import detect_brand
        return detect_brand(card.title)[0] is not None

    def parse_detail(self, url: str, html: str) -> dict | None:
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        product = {}
        for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(tag.string or "{}")
            except (ValueError, TypeError):
                continue
            for node in (data if isinstance(data, list) else [data]):
                if isinstance(node, dict) and node.get("@type") == "Product":
                    product = node
        offer = product.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        title = product.get("name") or (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else url)
        desc = product.get("description") or ""
        if not desc:
            el = soup.select_one(".description, [itemprop=description], #description")
            desc = el.get_text(" ", strip=True) if el else ""
        imgs = product.get("image") or []
        imgs = imgs if isinstance(imgs, list) else [imgs]
        imgs += [m["content"] for m in soup.select('meta[property="og:image"]') if m.get("content")]
        availability = str(offer.get("availability", "")).rsplit("/", 1)[-1]
        currency = (offer.get("priceCurrency") or "HUF").upper()
        price = to_int_huf(offer.get("price")) if currency == "HUF" else None
        status = "ended" if availability in ("OutOfStock", "SoldOut", "Discontinued") else "active"
        return {
            "url": url, "title": title[:300], "description": re.sub(r"\s+", " ", desc)[:4000],
            "sale_type": "alku", "price_huf": price, "price_kind": "kert ar", "currency": currency,
            "status": status, "status_reason": f"készletjelzés: {availability or 'nincs'}",
            "images": [u for u in dict.fromkeys(i for i in imgs if isinstance(i, str) and i.startswith("http"))][:8],
        }
