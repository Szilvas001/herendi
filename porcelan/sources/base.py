"""Forrás-interfész: feladatok (keresés/kategória/részletek) és oldalelemzés."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BUDAPEST = ZoneInfo("Europe/Budapest")


@dataclass
class Task:
    kind: str                  # search / category / detail
    url: str
    query: str | None = None   # a lefedettség "scope"-ja (kifejezés vagy kategória)
    page: int = 1
    priority: int = 50


@dataclass
class Card:
    """Egy hirdetés a találati listában (részletes oldal letöltése nélkül)."""
    source_id: str
    url: str
    title: str
    price_huf: int | None = None
    sale_type: str | None = None      # fix / alku / aukcio / None
    expired: bool = False
    image_url: str | None = None
    category: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class IndexPage:
    cards: list[Card]
    reported_total: int | None = None
    has_next: bool | None = None       # None: nem eldönthető a HTML-ből
    categories: list[str] = field(default_factory=list)


class Source:
    name = "base"
    market = "HU"
    per_page_hint = 60

    def seed_tasks(self, full_catalog: bool = False) -> list[Task]:
        raise NotImplementedError

    def page_task(self, task: Task, page: int) -> Task:
        raise NotImplementedError

    def parse_index(self, url: str, html: str) -> IndexPage:
        raise NotImplementedError

    def detail_url(self, card_or_url) -> str:
        return card_or_url.url if isinstance(card_or_url, Card) else card_or_url

    def parse_detail(self, url: str, html: str) -> dict | None:
        raise NotImplementedError

    def is_relevant_card(self, card: Card) -> bool:
        return True

    def is_relevant_category(self, url: str, label: str = "") -> bool:
        return False


# --- közös segédek --------------------------------------------------------------
_HU_DT = re.compile(r"(\d{4})[.\-/ ]+(\d{1,2})[.\-/ ]+(\d{1,2})\.?(?:\s+(\d{1,2}):(\d{2}))?")


def parse_hu_datetime(raw: str | None) -> str | None:
    """'2026.10.03. 19:11' -> ISO 8601 UTC-ben (a forrás budapesti idejéből)."""
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        return (dt if dt.tzinfo else dt.replace(tzinfo=BUDAPEST)).astimezone(timezone.utc).isoformat()
    except ValueError:
        pass
    m = _HU_DT.search(raw)
    if not m:
        return None
    y, mo, d, hh, mm = m.groups()
    try:
        dt = datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), tzinfo=BUDAPEST)
    except ValueError:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def to_int_huf(raw) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        v = int(round(raw))
    else:
        s = str(raw).replace("\xa0", " ")
        m = re.search(r"\d[\d\s.]*(?:,\d+)?", s)
        if not m:
            return None
        digits = m.group(0).split(",")[0]
        digits = re.sub(r"[^\d]", "", digits)
        if not digits:
            return None
        v = int(digits)
    return v if 0 < v <= 500_000_000 else None
