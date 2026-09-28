"""Vatera adapter: keresés névváltozatokra, kategóriabejárás, lapozás, termékoldal.

A találati oldalon a Vatera kártyái `data-product-id`, `data-gtm-name`,
`data-gtm-price`, `data-gtm-auction-type` (fix_price / bid) és `data-expired`
attribútumot hordoznak (a 2026-09-i élő futások alapján). A termékoldali
eladási típus, ár és készletjelzés a meglévő, élesben hangolt `parsing`
modulból jön.
"""
from __future__ import annotations

import json
import re
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from .. import parsing, settings
from ..text import norm
from .base import Card, IndexPage, Source, Task, parse_hu_datetime, to_int_huf

PRODUCT_RE = re.compile(r"-(\d{6,})\.html$")
_TOTAL_RE = re.compile(r"(\d{1,3}(?:[ . ]\d{3})*|\d+)\s*(?:db\s+)?(?:találat|termék|hirdetés)", re.I)
_AUCTION_TYPES = {"bid": "aukcio", "fix_price": "fix", "auction": "aukcio"}
_IMG_HOST_RE = re.compile(r"https?://[^\"'\s)]*(?:vatera|vimg|img)[^\"'\s)]*\.(?:jpe?g|png|webp)", re.I)


class VateraSource(Source):
    name = "vatera"
    market = "HU"

    def __init__(self):
        cfg = settings.get("vatera")
        self.base = cfg["base_url"].rstrip("/")
        self.search_path = cfg["search_path"]
        self.cfg = cfg

    # -- feladatok ------------------------------------------------------------
    def search_url(self, query: str, page: int = 1) -> str:
        params = {"q": query}
        if page > 1:
            params["p"] = page
        return f"{self.base}{self.search_path}?{urlencode(params)}"

    def seed_tasks(self, full_catalog: bool = False) -> list[Task]:
        tasks = []
        for q in self.cfg["queries_herend"] + self.cfg["queries_zsolnay"]:
            tasks.append(Task("search", self.search_url(q), f"query:{q}", 1, 10))
        for q in self.cfg.get("queries_generic", []):
            tasks.append(Task("search", self.search_url(q), f"query:{q}", 1, 40))
        for url in self.cfg.get("seed_categories", []):
            tasks.append(Task("category", url, f"category:{url}", 1, 20))
        if full_catalog:
            tasks.append(Task("category", self.base + "/", "category:root", 1, 90))
        return tasks

    def general_tasks(self) -> list[Task]:
        """Általános porcelán/kerámia korpusz (előtanításhoz), márkanév nélkül is."""
        return [Task("search", self.search_url(q), f"general:{q}", 1, 60)
                for q in self.cfg.get("queries_general_corpus", [])]

    def page_task(self, task: Task, page: int) -> Task:
        parsed = urlparse(task.url)
        qs = parse_qs(parsed.query)
        qs["p"] = [str(page)]
        url = urlunparse(parsed._replace(query=urlencode({k: v[0] for k, v in qs.items()})))
        return Task(task.kind, url, task.query, page, task.priority + min(page, 30) // 10)

    # -- találati oldal -------------------------------------------------------
    def parse_index(self, url: str, html: str) -> IndexPage:
        soup = BeautifulSoup(html or "", "html.parser")
        cards: dict[str, Card] = {}
        for el in soup.select("[data-product-id]"):
            pid = (el.get("data-product-id") or "").strip()
            if not pid.isdigit():
                continue
            a = el.select_one("a.product_link[href]") or el.select_one("a[href]")
            href = urljoin(self.base, a["href"]) if a else None
            if not href or not PRODUCT_RE.search(urlparse(href).path):
                continue
            href = href.split("#")[0].split("?")[0]
            title = el.get("data-gtm-name") or (a.get("title") if a else None) or (a.get_text(" ", strip=True) if a else "")
            price = to_int_huf(el.get("data-gtm-price"))
            currency = (el.get("data-gtm-currency") or "HUF").upper()
            if currency not in ("HUF", "FT"):
                price = None  # nem forintos ár: részletes oldalon kezeljük
            img = el.select_one("img")
            image = None
            if img:
                image = img.get("data-src") or img.get("data-original") or img.get("src")
                if image and image.startswith("data:"):
                    image = None
                if image:
                    image = urljoin(self.base, image)
            cards.setdefault(pid, Card(
                source_id=pid, url=href, title=(title or "").strip(), price_huf=price,
                sale_type=_AUCTION_TYPES.get((el.get("data-gtm-auction-type") or "").strip()),
                expired=(el.get("data-expired") or "0") not in ("0", "", "false"),
                image_url=image, category=el.get("data-gtm-category"),
                extra={"card_currency": currency}))
        if not cards:  # tartalék: régi/egyszerű HTML, csak linkek
            for a in soup.select("a[href]"):
                href = urljoin(self.base, a["href"]).split("#")[0].split("?")[0]
                m = PRODUCT_RE.search(urlparse(href).path)
                if m and urlparse(href).netloc.endswith("vatera.hu"):
                    cards.setdefault(m.group(1), Card(m.group(1), href, a.get_text(" ", strip=True)))

        text = soup.get_text(" ", strip=True)
        total = None
        m = _TOTAL_RE.search(text)
        if m:
            total = int(re.sub(r"\D", "", m.group(1)))
        has_next = None
        if soup.select_one("a[rel=next], link[rel=next], .pagination .next a, a.next"):
            has_next = True
        elif soup.select_one(".pagination, nav[aria-label*=agin]"):
            has_next = False

        cats = []
        for a in soup.select("a[href]"):
            href = urljoin(self.base, a["href"]).split("#")[0]
            p = urlparse(href)
            if not p.netloc.endswith("vatera.hu") or PRODUCT_RE.search(p.path):
                continue
            if p.path in ("", "/") or any(x in p.path for x in ("/listings/", "/user", "/login", "/help",
                                                               "/sugo", "/kosar", "/regisztracio", ".php")):
                continue
            cats.append(href.split("?")[0])
        return IndexPage(list(cards.values()), total, has_next, sorted(set(cats)))

    def is_relevant_category(self, url: str, label: str = "") -> bool:
        keywords = [norm(k) for k in self.cfg.get("category_keywords", [])]
        text = norm(label + " " + urlparse(url).path.replace("-", " ").replace("/", " "))
        return any(k in text for k in keywords)

    def is_relevant_card(self, card: Card) -> bool:
        from ..text import detect_brand
        return detect_brand(card.title)[0] is not None

    # -- termékoldal ----------------------------------------------------------
    def parse_detail(self, url: str, html: str) -> dict | None:
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        availability = parsing.extract_availability(soup, url)
        jsonld = _jsonld_nodes(soup)
        images = _images(soup, jsonld)
        breadcrumbs = _breadcrumbs(jsonld)
        for tag in soup.find_all(["script", "style", "noscript", "svg"]):
            tag.decompose()
        title = parsing.extract_title(soup, url)
        text = soup.get_text(" ", strip=True).replace("\xa0", " ")
        text_norm = parsing.norm(f"{title} {text}")
        sale_type, offer_possible = parsing.detect_sale_type(html, text_norm)
        prices = parsing.extract_prices(html, text_norm, sale_type)
        m = re.search(r"Eladó leírása a termékről(.*?)(?:Szállítási feltételek|Fizetési feltételek|$)", text, re.S)
        description = (m.group(1) if m else parsing.extract_description(soup)).strip()
        description = re.sub(r"\s+", " ", description)[:4000]
        shipping = None
        ms = re.search(r"(?:szállítás|postaköltség|házhozszállítás)[^0-9]{0,40}?(\d[\d\s.]{2,})\s*Ft", text, re.I)
        if ms:
            shipping = to_int_huf(ms.group(1))
        mq = re.search(r"(?:készleten|elérhető mennyiség|mennyiség)\s*:?\s*(\d{1,4})\s*db", text, re.I)
        sold_text = bool(re.search(r"\b(elkelt|a termék elkelt|eladva|sikeresen zárult)\b", text, re.I))
        ended_text = bool(re.search(r"(lejárt|lezárult|befejeződött)\s+(hirdetés|aukció)|az aukció véget ért", text, re.I))
        end_iso = parse_hu_datetime(parsing.extract_end_time(text))

        status, reason = "active", "készletjelzés: " + availability
        bids = prices.get("bid_count") or 0
        if availability == "unavailable" or sold_text or ended_text:
            if sale_type == "aukcio":
                if bids > 0:
                    status, reason = "sold", "aukció lezárult licittel (záró licit, nem igazolt fizetés)"
                else:
                    status, reason = "ended", "aukció licit nélkül zárult"
            elif sold_text:
                status, reason = "sold", "a termékoldal elkeltnek jelzi"
            else:
                status, reason = "ended", "nem elérhető / lejárt (nem bizonyított eladás)"

        return {
            "url": url,
            "title": title[:300],
            "description": description,
            "category": " > ".join(breadcrumbs) or None,
            "sale_type": sale_type,
            "offer_possible": offer_possible,
            "price_huf": prices.get("price_huf"),
            "price_kind": prices.get("price_kind"),
            "current_bid_huf": prices.get("current_bid_huf") if sale_type == "aukcio" else None,
            "start_bid_huf": prices.get("start_bid_huf") if sale_type == "aukcio" else None,
            "buy_now_huf": prices.get("buy_now_huf"),
            "bid_count": prices.get("bid_count") if sale_type == "aukcio" else None,
            "end_time": end_iso,
            "shipping_huf": shipping,
            "quantity": int(mq.group(1)) if mq else None,
            "seller": parsing.extract_seller(text),
            "status": status,
            "status_reason": reason,
            "images": images,
            "availability": availability,
        }


def _jsonld_nodes(soup) -> list[dict]:
    nodes = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "{}")
        except (ValueError, TypeError):
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                nodes.append(node)
                if isinstance(node.get("@graph"), list):
                    stack.extend(node["@graph"])
    return nodes


def _images(soup, jsonld) -> list[str]:
    urls = []
    for node in jsonld:
        if node.get("@type") == "Product":
            img = node.get("image")
            for u in (img if isinstance(img, list) else [img]):
                if isinstance(u, dict):
                    u = u.get("url")
                if isinstance(u, str):
                    urls.append(u)
    for meta in soup.select('meta[property="og:image"], meta[name="twitter:image"]'):
        if meta.get("content"):
            urls.append(meta["content"])
    for img in soup.select("[data-zoom-image], .gallery img, .product-image img, img[data-large]"):
        for attr in ("data-zoom-image", "data-large", "data-src", "src"):
            if img.get(attr) and not img[attr].startswith("data:"):
                urls.append(img[attr])
                break
    out = []
    for u in urls:
        u = u.strip()
        if u.startswith("//"):
            u = "https:" + u
        if u.startswith("http") and u not in out and not re.search(r"logo|icon|sprite|placeholder", u, re.I):
            out.append(u)
    return out[: settings.get("crawl.max_images_per_listing", 8)]


def _breadcrumbs(jsonld) -> list[str]:
    for node in jsonld:
        if node.get("@type") == "BreadcrumbList":
            items = sorted(node.get("itemListElement", []), key=lambda x: x.get("position", 0))
            names = []
            for it in items:
                name = it.get("name") or (it.get("item") or {}).get("name") if isinstance(it.get("item"), dict) else it.get("name")
                if name:
                    names.append(str(name))
            return names
    return []
