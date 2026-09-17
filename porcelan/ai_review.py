"""Claude Opus 5 elemzés: a 3 részre bontott hirdetéslista értékelése.

A scraper kimenete eladási típusonként (aukció / fix / alku) külön megy fel az
API-ra, így a modell ugyanazt a tételt a saját kontextusában értékeli.
"""
from __future__ import annotations

import json
import logging
import os

from . import config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
Te egy magyar és nemzetközi porcelánpiacot ismerő szakértő vagy: Herendi és \
Zsolnay tételek beszerzési oldalán dolgozol.

Feladatod a kapott Vatera-hirdetések átnézése, és KIZÁRÓLAG azoknak a \
kiválasztása, amelyek:
  (A) áron aluliak a magyar piachoz képest, VAGY
  (B) amerikai / nyugat-európai piacon (eBay US/DE, Etsy, 1stDibs, \
Replacements, aukciósházak) jelentősen magasabb áron értékesíthetők.

Értékelési szempontok:
- Minta/dekor (pl. Herendi Apponyi, Rothschild, Victoria, Waldstein; Zsolnay \
eozin, szecesszió, pirogranit) és annak nyugati keresettsége.
- Jelzés/festés (pajzspecsét, kézzel festett, aranyozott), kor, ritkaság.
- Állapot: sérülés, csorba, repedés, javítás erősen csökkenti az értéket.
- Készlet vs. egyedi darab; szállíthatóság (törékeny, nagy méret) és a \
nemzetközi postázás kockázata.
- Az eladási típus: aukciónál az aktuális licit még emelkedhet, alkuképes \
tételnél az irányárból lehet lealkudni, fix árasnál az ár adott.

Kemény szabályok:
- Csak a bemenetben ténylegesen szereplő hirdetéseket adhatod vissza, a \
kapott `url` és `listing_id` mezők pontos másolatával. URL-t kitalálni TILOS.
- Ha egy tétel adata hiányos (nincs ár, nincs leírás), akkor csak akkor \
válaszd ki, ha a cím önmagában is egyértelműen értékes darabra utal, és ezt \
írd is oda a kockázatok közé.
- Ha egy listában nincs jó tétel, üres `talalatok` tömböt adj vissza. \
Ne töltsd fel gyenge találatokkal.
- Az EUR becslés a reálisan elérhető nyugati eladási ár sávja legyen \
(nem gyűjtői csúcsár), a hirdetés árának levonása nélkül.
- Az indoklás magyarul, tömören (2-4 mondat), konkrétumokkal.\
"""

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "talalatok": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "listing_id": {"type": "string"},
                    "url": {"type": "string"},
                    "cim": {"type": "string"},
                    "marka": {"type": "string"},
                    "eladasi_tipus": {"type": "string"},
                    "ar_huf": {"type": "integer"},
                    "kategoria": {
                        "type": "string",
                        "enum": ["aron_aluli", "nyugati_piac", "mindketto"],
                    },
                    "becsult_ertek_eur_min": {"type": "integer"},
                    "becsult_ertek_eur_max": {"type": "integer"},
                    "bizalom": {"type": "string", "enum": ["magas", "kozepes", "alacsony"]},
                    "indoklas": {"type": "string"},
                    "kockazatok": {"type": "string"},
                },
                "required": [
                    "listing_id", "url", "cim", "marka", "eladasi_tipus", "ar_huf",
                    "kategoria", "becsult_ertek_eur_min", "becsult_ertek_eur_max",
                    "bizalom", "indoklas", "kockazatok",
                ],
                "additionalProperties": False,
            },
        },
        "osszegzes": {"type": "string"},
    },
    "required": ["talalatok", "osszegzes"],
    "additionalProperties": False,
}

# A modellnek felküldött mezők (a description rövidítve).
PAYLOAD_FIELDS = [
    "listing_id", "brand", "title", "sale_type", "price_huf", "price_kind",
    "buy_now_huf", "start_bid_huf", "current_bid_huf", "bid_count",
    "offer_possible", "end_time", "damage_flags", "suspect_flags",
    "decor_hints", "url",
]


class AiUnavailable(RuntimeError):
    """Nincs API kulcs vagy nincs telepítve az anthropic csomag."""


def _client():
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover - telepítési hiba
        raise AiUnavailable("Az `anthropic` csomag nincs telepítve "
                            "(pip install -r requirements.txt).") from exc
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise AiUnavailable("Nincs ANTHROPIC_API_KEY a környezetben.")
    return anthropic.Anthropic()


def to_payload(record: dict) -> dict:
    item = {k: record.get(k) for k in PAYLOAD_FIELDS}
    item["description"] = (record.get("description") or "")[:config.AI_DESC_CHARS]
    return item


def chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _extract_json(message) -> dict:
    text = next((b.text for b in message.content if b.type == "text"), "")
    return json.loads(text)


def _beta_unsupported(exc: Exception) -> bool:
    """Igaz, ha a hiba a fallback betára utal (régi SDK / nem engedélyezett)."""
    if isinstance(exc, TypeError):
        return True
    if getattr(exc, "status_code", None) == 400:
        return True
    text = str(exc).lower()
    return any(k in text for k in ("beta", "fallback", "unexpected keyword"))


def _call(client, sale_type: str, records: list[dict], part_idx: int,
          total_parts: int) -> dict:
    payload = [to_payload(r) for r in records]
    label = config.SALE_TYPE_LABELS.get(sale_type, sale_type)

    user_text = (
        f"Eladási típus: {label} ({sale_type}). "
        f"Ez a {part_idx}/{total_parts}. adag ebből a típusból, {len(payload)} hirdetés.\n\n"
        "Hirdetések JSON-ban:\n"
        f"{json.dumps(payload, ensure_ascii=False)}\n\n"
        "Add vissza a megadott séma szerint azokat a tételeket, amelyek áron "
        "aluliak vagy nyugati piacon jól értékesíthetők."
    )

    kwargs = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=config.CLAUDE_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "high",
            "format": {"type": "json_schema", "schema": RESULT_SCHEMA},
        },
        messages=[{"role": "user", "content": user_text}],
    )

    # Szerveroldali fallback: ha a modell elutasítja a kérést, a szerver
    # automatikusan másik modellre irányít.
    try:
        with client.beta.messages.stream(
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
        ) as stream:
            message = stream.get_final_message()
    except Exception as exc:
        if not _beta_unsupported(exc):
            raise
        log.debug("Fallback beta nem használható (%s), sima hívás következik.", exc)
        with client.messages.stream(**kwargs) as stream:
            message = stream.get_final_message()

    if getattr(message, "stop_reason", None) == "refusal":
        details = getattr(message, "stop_details", None)
        raise RuntimeError(f"A modell elutasította a kérést: {details}")

    usage = getattr(message, "usage", None)
    if usage:
        log.info("      token: be=%s ki=%s", usage.input_tokens, usage.output_tokens)
    return _extract_json(message)


def analyse(buckets: dict[str, list[dict]], chunk_size: int | None = None,
            client=None) -> dict:
    """A 3 részt (aukció / fix / alku) külön-külön átadja a modellnek.

    Visszatér: {"talalatok": [...], "osszegzesek": {sale_type: str}, "hibak": [...]}
    """
    chunk_size = chunk_size or config.AI_CHUNK_SIZE
    client = client or _client()

    valid_urls = {r["url"] for t in config.SALE_TYPES for r in buckets.get(t, [])}
    by_url = {r["url"]: r for t in config.SALE_TYPES for r in buckets.get(t, [])}

    picks: list[dict] = []
    summaries: dict[str, str] = {}
    errors: list[str] = []

    for sale_type in config.SALE_TYPES:
        records = buckets.get(sale_type, [])
        if not records:
            log.info("   %s: nincs tétel, kihagyva.", config.SALE_TYPE_LABELS[sale_type])
            continue

        parts = list(chunks(records, chunk_size))
        log.info("   %s: %d tétel, %d API hívás (%s).",
                 config.SALE_TYPE_LABELS[sale_type], len(records), len(parts),
                 config.CLAUDE_MODEL)

        part_summaries = []
        for idx, part in enumerate(parts, 1):
            try:
                result = _call(client, sale_type, part, idx, len(parts))
            except Exception as exc:
                msg = f"{sale_type} {idx}/{len(parts)}: {exc}"
                log.error("   HIBA – %s", msg)
                errors.append(msg)
                continue

            for pick in result.get("talalatok", []):
                url = pick.get("url", "")
                if url not in valid_urls:
                    log.warning("   Kihagyva (nem a bemenetből való URL): %s", url)
                    continue
                source = by_url[url]
                pick["sale_type"] = sale_type
                pick["ar_huf_scrape"] = source.get("price_huf")
                pick["allapot_jelzok"] = source.get("damage_flags")
                picks.append(pick)
            part_summaries.append(result.get("osszegzes", ""))
            log.info("      %d/%d rész kész: %d javaslat.",
                     idx, len(parts), len(result.get("talalatok", [])))

        summaries[sale_type] = " ".join(s for s in part_summaries if s)

    order = {"magas": 0, "kozepes": 1, "alacsony": 2}
    picks.sort(key=lambda p: (order.get(p.get("bizalom"), 3),
                              -(p.get("becsult_ertek_eur_max") or 0)))
    return {"talalatok": picks, "osszegzesek": summaries, "hibak": errors}
