"""Vatera termékoldal elemzése: eladási típus, ár, márka, állapot."""
from __future__ import annotations

import json
import re
import unicodedata

from bs4 import BeautifulSoup

from . import config

# ---------------------------------------------------------------------------
# Szöveg normalizálás
# ---------------------------------------------------------------------------


def strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(ch for ch in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(ch))


def norm(s: str) -> str:
    """Kisbetűs, ékezet nélküli, egyszeres szóközös szöveg – kereséshez."""
    s = (s or "").replace("\xa0", " ")
    s = strip_accents(s.lower())
    return re.sub(r"\s+", " ", s).strip()


def visible_text(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return soup.get_text(" ", strip=True).replace("\xa0", " ")


# ---------------------------------------------------------------------------
# Eladási típus
# ---------------------------------------------------------------------------
AUCTION_CUES = [
    "aktualis licit", "jelenlegi licit", "licitalok", "licit lepcso", "licitlepcso",
    "kikialtasi ar", "legyel te az elso licitalo", "licitmegbizas", "licitek szama",
    "licitalasi elozmenyek", "licitalj", "licittortenet",
]
OFFER_CUES = [
    "ajanlatot tehetsz", "ajanlatot teszek", "ajanlattetel", "ajanlatot vart",
    "alkudhato", "alkukepes", "alku lehetseges", "iranyar", "irany ar",
    "megegyezes szerint", "ar megegyezes", "megegyezunk", "alkura van lehetoseg",
]
FIX_CUES = ["fix ar", "azonnali vetel", "kosarba teszem", "kosarba"]

# Az élő Vatera termékoldal saját jelölése. A látható szöveg (menü, felugró
# ablakok: "Licitáljon most", "Irányár:") minden oldalon ugyanaz, ezért ha ez
# a jelölés megvan, csak erre építünk.
_GTM_TYPE_RE = re.compile(r'class="[^"]*\bgtm-auction-type\b[^"]*"[^>]*>\s*(\w+)\s*<')
_BESTOFFER_RE = re.compile(r'"product_bestofferminpercent"\s*:\s*(?!null)\d|id="bestofferform"')


def detect_sale_type(html: str, text_norm: str) -> tuple[str, bool]:
    """(eladási típus, alkuképes-e) – a 3 kosár (aukció / fix / alku) alapja.

    Elsődleges jel a `gtm-auction-type` span (`bid` / `fix_price`) és az
    ajánlattételi űrlap (`bestofferform`). Ha ezek hiányoznak, a `fix_price`
    ill. `bid` tokenre és a látható szöveg kulcsszavaira támaszkodunk.
    """
    gtm = _GTM_TYPE_RE.search(html or "")
    if gtm and gtm.group(1) in ("bid", "fix_price"):
        offer_possible = bool(_BESTOFFER_RE.search(html))
        if gtm.group(1) == "bid":
            return config.SALE_AUCTION, offer_possible
        return (config.SALE_OFFER if offer_possible else config.SALE_FIX), offer_possible

    html_norm = norm(html)
    has_fix_token = bool(re.search(r"\bfix_price\b", html_norm))
    has_bid_token = bool(re.search(r"\bbid\b", html_norm))

    auction_cue = any(c in text_norm for c in AUCTION_CUES)
    offer_cue = any(c in text_norm for c in OFFER_CUES)
    fix_cue = any(c in text_norm for c in FIX_CUES)

    if auction_cue or (has_bid_token and not has_fix_token):
        return config.SALE_AUCTION, offer_cue
    if has_fix_token or fix_cue:
        return (config.SALE_OFFER if offer_cue else config.SALE_FIX), offer_cue
    if offer_cue:
        return config.SALE_OFFER, True
    return config.SALE_UNKNOWN, offer_cue


# ---------------------------------------------------------------------------
# Ár
# ---------------------------------------------------------------------------
_AMOUNT = r"([0-9][0-9\s. ]{2,})\s*(?:ft|huf|forint)"


def _to_int(raw: str) -> int | None:
    digits = re.sub(r"[^\d]", "", raw or "")
    if not digits:
        return None
    try:
        value = int(digits)
    except ValueError:
        return None
    return value if 100 <= value <= 100_000_000 else None


# Ezek előzménye esetén az összeg nem a termék ára (szállítás, díj stb.).
SHIPPING_CUES = ["szallitas", "postakoltseg", "posta", "utanvet", "csomagolas",
                 "futar", "atvetel", "foxpost", "mpl", "kezelesi"]


def amount_after(text_norm: str, labels: list[str]) -> int | None:
    """Címke utáni összeg, pl. 'fix ar: 12 000 Ft' -> 12000.

    A szállítási díjakat kiszűrjük (a címke előtti 40 karakter alapján).
    """
    for label in labels:
        for m in re.finditer(rf"\b{re.escape(label)}\b\s*:?\s*{_AMOUNT}", text_norm):
            prefix = text_norm[max(0, m.start() - 40):m.start()]
            if any(cue in prefix for cue in SHIPPING_CUES):
                continue
            value = _to_int(m.group(1))
            if value:
                return value
    return None


def any_amount(text_norm: str) -> int | None:
    values = [v for v in (_to_int(m) for m in re.findall(_AMOUNT, text_norm)) if v]
    return max(values) if values else None


def jsonld_offer(html: str) -> tuple[int | None, str | None]:
    """(ár, JSON-LD nyers részlet) – ha a termékoldalon van strukturált adat."""
    soup = BeautifulSoup(html or "", "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.get_text(strip=True) or "{}")
        except (ValueError, TypeError):
            continue
        for node in (data if isinstance(data, list) else [data]):
            if not isinstance(node, dict):
                continue
            offers = node.get("offers")
            offer_list = offers if isinstance(offers, list) else [offers]
            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                price = offer.get("price")
                if price is None:
                    continue
                try:
                    value = int(float(str(price).replace(" ", "").replace(",", ".")))
                except ValueError:
                    continue
                if 100 <= value <= 100_000_000:
                    return value, json.dumps(node, ensure_ascii=False)[:1500]
    return None, None


def extract_prices(html: str, text_norm: str, sale_type: str) -> dict:
    """Ár mezők eladási típus szerint."""
    jsonld_price, _ = jsonld_offer(html)

    fix_price = amount_after(text_norm, ["fix ar", "fix ara", "vetelar", "ara"])
    buy_now = amount_after(text_norm, ["azonnali vetel ara", "azonnali vetel", "villamar"])
    current_bid = amount_after(text_norm, ["aktualis licit", "jelenlegi licit", "legmagasabb licit"])
    start_bid = amount_after(text_norm, ["kikialtasi ar", "indulo ar", "minimum ar", "minimalar"])

    if sale_type == config.SALE_AUCTION:
        price = current_bid or start_bid or jsonld_price or buy_now
        price_kind = ("aktualis licit" if current_bid else
                      "kikialtasi ar" if start_bid else "egyeb")
    else:
        price = jsonld_price or fix_price or buy_now or any_amount(text_norm)
        price_kind = "fix ar" if (jsonld_price or fix_price) else "egyeb"

    bids = None
    m = re.search(r"(\d+)\s*(?:db\s*)?licit", text_norm)
    if m:
        bids = int(m.group(1))

    return {
        "price_huf": price,
        "price_kind": price_kind,
        "buy_now_huf": buy_now,
        "start_bid_huf": start_bid,
        "current_bid_huf": current_bid,
        "bid_count": bids,
    }


# ---------------------------------------------------------------------------
# Márka / relevancia
# ---------------------------------------------------------------------------


def detect_brand(text_norm: str) -> str | None:
    for brand, tokens in config.BRAND_TOKENS.items():
        if any(re.search(rf"\b{re.escape(norm(tok))}\w*", text_norm) for tok in tokens):
            return brand
    return None


def _hits(text_norm: str, cues: list[str]) -> list[str]:
    return [c for c in cues if norm(c) in text_norm]


def relevance(title: str, text_norm: str) -> dict:
    """Eldönti, hogy a keresett (profil szerinti) tétel-e, és miért nem, ha nem."""
    title_norm = norm(title)
    brand = detect_brand(title_norm)
    if not brand and not config.BRAND_IN_TITLE_ONLY:
        brand = detect_brand(text_norm)
    reasons: list[str] = []

    if not brand:
        reasons.append(config.NO_BRAND_LABEL)

    fake = _hits(title_norm, config.FAKE_CUES)
    if fake:
        reasons.append(f"{config.FAKE_LABEL}: " + ", ".join(fake))

    non_porcelain = _hits(title_norm, config.NON_PORCELAIN_CUES)
    if non_porcelain:
        reasons.append(f"{config.NON_ITEM_LABEL}: " + ", ".join(non_porcelain))

    return {
        "brand": brand,
        "accepted": not reasons,
        "reject_reason": "; ".join(reasons),
        "suspect_flags": ", ".join(_hits(text_norm, config.SUSPECT_CUES)),
        "damage_flags": ", ".join(_hits(text_norm, config.DAMAGE_CUES)),
        "decor_hints": ", ".join(_hits(text_norm, config.DECOR_HINTS)),
    }


# ---------------------------------------------------------------------------
# Egyéb mezők
# ---------------------------------------------------------------------------


def listing_id(url: str) -> str | None:
    m = re.search(r"-(\d{6,})\.html", url or "")
    return m.group(1) if m else None


def extract_title(soup: BeautifulSoup, url: str) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(" ", strip=True)
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(" ", strip=True)
    return url


def extract_description(soup: BeautifulSoup) -> str:
    """Az eladó leírása / termék sajátosságai blokk, ha megtalálható."""
    wanted = ["eladó leírása", "termékleírás", "termék sajátosságai", "leírás"]
    for el in soup.find_all(["h1", "h2", "h3", "h4", "div", "span", "p", "strong"]):
        label = norm(el.get_text(" ", strip=True))
        if not label or len(label) > 80:
            continue
        if any(norm(w) in label for w in wanted):
            container = el
            for _ in range(4):
                if container.parent is None:
                    break
                container = container.parent
                if len(container.get_text(" ", strip=True)) > 250:
                    break
            return container.get_text(" ", strip=True)[:4000]
    main = soup.find("main") or soup.find("article") or soup.body
    return (main.get_text(" ", strip=True)[:4000] if main else "")


def extract_seller(text: str) -> str | None:
    m = re.search(r"(?:elad[óo]|felhaszn[áa]l[óo]|elad[óo] neve)\s*:\s*([A-Za-z0-9._\-]{3,30})", text)
    return m.group(1) if m else None


def extract_end_time(text: str) -> str | None:
    """Aukció/hirdetés vége – 'Az aukció vége: 2026. 03. 05. 15:38'."""
    m = re.search(r"(?:aukci[óo] v[ée]ge|hirdet[ée]s v[ée]ge|h[áa]tral[ée]v[őo] id[őo])\s*:?\s*"
                  r"([0-9]{4}[.\-/ ]+[0-9]{1,2}[.\-/ ]+[0-9]{1,2}\.?(?:\s+[0-9]{1,2}:[0-9]{2})?)",
                  text, flags=re.IGNORECASE)
    return m.group(1).strip() if m else None


def parse_listing(url: str, html: str) -> dict | None:
    """Egy termékoldalból strukturált rekord (elfogadott és elutasított is)."""
    if not html:
        return None

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = extract_title(soup, url)
    description = extract_description(soup)
    text = soup.get_text(" ", strip=True).replace("\xa0", " ")
    text_norm = norm(f"{title} {text}")

    sale_type, offer_possible = detect_sale_type(html, text_norm)
    prices = extract_prices(html, text_norm, sale_type)
    rel = relevance(title, text_norm)

    record = {
        "listing_id": listing_id(url),
        "brand": rel["brand"],
        "title": title[:200],
        "sale_type": sale_type,
        "sale_type_label": config.SALE_TYPE_LABELS.get(sale_type, sale_type),
        "offer_possible": offer_possible,
        **prices,
        "end_time": extract_end_time(text),
        "seller": extract_seller(text),
        "damage_flags": rel["damage_flags"],
        "suspect_flags": rel["suspect_flags"],
        "decor_hints": rel["decor_hints"],
        "description": re.sub(r"\s+", " ", description)[:2000],
        "url": url,
        "accepted": rel["accepted"],
        "reject_reason": rel["reject_reason"],
    }
    return record
