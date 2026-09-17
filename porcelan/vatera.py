"""Vatera piactér scraper: keresőoldalak -> termékoldalak -> rekordok."""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from . import config
from .httpclient import HttpClient
from .parsing import parse_listing

log = logging.getLogger(__name__)

PRODUCT_RE = re.compile(config.PRODUCT_URL_RE)


def search_url(term: str, page: int = 1) -> str:
    return f"{config.LISTING_URL}?{urlencode({'q': term, 'p': page})}"


def extract_product_links(html: str) -> list[str]:
    """Termékoldal linkek egy találati oldalról (menü/footer linkek nélkül)."""
    if not html:
        return []

    found: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if href:
            found.add(urljoin(config.BASE_URL, href))

    # Tartalék: néha a linkek JS-ből renderelődnek, de ott vannak a HTML-ben.
    for m in re.findall(r"https?://(?:www\.|ssl\.)?vatera\.hu/[^\s\"'<>]+-\d{6,}\.html", html):
        found.add(m)

    out: list[str] = []
    for url in sorted(found):
        parsed = urlparse(url)
        if not parsed.netloc.endswith("vatera.hu"):
            continue
        if not PRODUCT_RE.search(parsed.path):
            continue
        # A "...html#bidlink" ugyanaz a hirdetés: query és fragment nélkül tároljuk.
        clean = url.split("#")[0].split("?")[0]
        if clean not in out:
            out.append(clean)
    return out


def collect_listing_urls(client: HttpClient, terms: list[str], max_pages: int) -> list[str]:
    """Keresőkifejezésenként végigmegy a találati oldalakon, linkeket gyűjt."""
    seen: set[str] = set()
    ordered: list[str] = []

    for term in terms:
        new_for_term = 0
        empty_pages = 0
        for page in range(1, max_pages + 1):
            html = client.get(search_url(term, page))
            if not html:
                log.warning("   '%s' %d. oldal: nincs válasz (blokkolás vagy vége)", term, page)
                break

            on_page = extract_product_links(html)
            if not on_page:                      # nincs több találati oldal
                break

            links = [u for u in on_page if u not in seen]
            if not links:                        # csak duplikátum: még egy oldalt nézünk
                empty_pages += 1
                if empty_pages >= 2:
                    break
                continue
            empty_pages = 0

            for url in links:
                seen.add(url)
                ordered.append(url)
            new_for_term += len(links)
        log.info("   '%s': +%d hirdetés (összesen %d)", term, new_for_term, len(ordered))

    return ordered


def scrape(terms: list[str] | None = None, max_pages: int | None = None,
           limit: int | None = None, workers: int | None = None,
           client: HttpClient | None = None) -> tuple[list[dict], list[dict]]:
    """Teljes Vatera scrape.

    Visszatér: (elfogadott rekordok, elutasított rekordok).
    """
    terms = terms or config.SEARCH_TERMS
    max_pages = config.MAX_PAGES if max_pages is None else max_pages
    workers = config.WORKERS if workers is None else workers
    client = client or HttpClient()

    log.info("Keresőoldalak bejárása (%d kifejezés, max %d oldal/kifejezés)...",
             len(terms), max_pages)
    urls = collect_listing_urls(client, terms, max_pages)
    if limit:
        urls = urls[:limit]
    log.info("Összesen %d egyedi hirdetés-URL.", len(urls))

    accepted: list[dict] = []
    rejected: list[dict] = []

    def work(url: str) -> dict | None:
        return parse_listing(url, client.get(url) or "")

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(work, url): url for url in urls}
        for idx, fut in enumerate(as_completed(futures), 1):
            try:
                record = fut.result()
            except Exception as exc:  # egy hibás oldal ne állítsa meg a futást
                log.debug("Hiba a feldolgozásnál (%s): %s", futures[fut], exc)
                continue
            if not record:
                continue
            (accepted if record["accepted"] else rejected).append(record)
            if idx % 50 == 0:
                log.info("   feldolgozva %d/%d | elfogadva %d | elutasítva %d",
                         idx, len(urls), len(accepted), len(rejected))

    log.info("Scrape kész: %d releváns, %d elutasított tétel. HTTP: %s",
             len(accepted), len(rejected), client.stats)
    return accepted, rejected


def split_by_sale_type(records: list[dict]) -> dict[str, list[dict]]:
    """A 3 kosár: aukció / fix áras / alkuképes (+ ismeretlen, külön)."""
    buckets: dict[str, list[dict]] = {t: [] for t in config.SALE_TYPES}
    buckets[config.SALE_UNKNOWN] = []
    for rec in records:
        buckets.setdefault(rec.get("sale_type", config.SALE_UNKNOWN), []).append(rec)
    return buckets
