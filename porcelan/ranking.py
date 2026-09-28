"""Alulárazottság, ajánlás/tartózkodás és rangsor – magyarázattal.

Két külön jelzés:
  - `below_value`: az ár a célpiaci becsült érték alatt van (árengedmény),
  - `profitable`: a költségek és adó után a KONZERVATÍV forgatókönyv is nyereséges.
Az USA-piaci érték alatti vétel és az USA-ba történő nyereséges továbbértékesítés
külön jelzés. A rendszer tartózkodik az ajánlástól, ha az azonosítás vagy az
adatok nem elégségesek.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import costs, settings

STALE_DAYS = 3


def _age_days(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - dt).total_seconds() / 86400


def missing_info(listing: dict, feats: dict, image_used: bool) -> list[str]:
    miss = []
    if not listing.get("description"):
        miss.append("nincs eladói leírás (részletes oldal nem ellenőrzött)")
    if not image_used:
        miss.append("nincs feldolgozott kép")
    if not feats.get("size_cm"):
        miss.append("méret ismeretlen")
    if feats.get("condition") == "ismeretlen":
        miss.append("állapot nincs megadva")
    if "marked" not in (feats.get("mark_flags") or ""):
        miss.append("talpjelzés nincs említve")
    if feats.get("object_type") in ("tea_set", "dinner_set") and not feats.get("pieces"):
        miss.append("készlet darabszáma ismeretlen")
    if feats.get("object_type") == "other":
        miss.append("tárgytípus nem azonosított")
    ident = feats.get("_identity") or {}
    if not ident.get("form_no"):
        miss.append("pontos termék (formaszám) nem azonosított – a pontos piaci árhoz ez kell")
    elif not ident.get("pattern_code"):
        miss.append("mintakód nem azonosított")
    return miss


def risks(listing: dict, feats: dict, est_market: dict | None) -> list[str]:
    r = []
    if feats.get("condition") == "serult":
        r.append("sérülésre utaló szó a hirdetésben: " + (feats.get("damage_flags") or ""))
    if feats.get("condition") == "javitott":
        r.append("javított / restaurált")
    if feats.get("suspect_flags"):
        r.append("gyanús jelzés: " + feats["suspect_flags"])
    if listing.get("sale_type") == "aukcio":
        r.append("aukció: az aktuális licit nem végleges vételár")
    if listing.get("brand_basis") == "text":
        r.append("a gyártó csak a leírásban szerepel, a címben nem")
    if est_market and est_market.get("basis") == "asking":
        r.append("a modell kínálati árakon tanult (kísérleti), nem realizált eladásokon")
    if est_market and est_market.get("top_similarity", 1) < 0.6:
        r.append("kevéssé hasonló összehasonlító tételek")
    age = _age_days(listing.get("last_checked") or listing.get("last_seen"))
    if age is not None and age > STALE_DAYS:
        r.append(f"a hirdetés {age:.0f} napja nem volt ellenőrizve – lehet, hogy már nem elérhető")
    title = (listing.get("title") or "").lower()
    if "doboz" in title and "bonbon" not in title:
        r.append("„doboz”: lehet, hogy csak a csomagolás, nem porcelán tárgy")
    r.append("az eredetiséget és az állapotot a rendszer nem igazolja")
    return r


def assess(listing: dict, estimate: dict, a: dict | None = None) -> dict:
    """Egy hirdetés teljes értékelése a dashboard számára."""
    a = a or costs.assumptions()
    rk = settings.get("ranking")
    feats = dict(estimate.get("features", {}))
    feats["_identity"] = estimate.get("identity")
    econ = costs.evaluate(listing, estimate, a)
    min_conf = rk["min_confidence_to_recommend"]
    result = {"markets": {}, "missing_info": missing_info(listing, feats, estimate.get("image_used", False)),
              "identity": estimate.get("identity")}
    for market, e in econ.items():
        est_m = estimate["markets"][market]
        abstain = []
        if listing.get("relevance") != "accepted" or not feats.get("brand"):
            abstain.append("gyártó nem azonosított")
        if e["confidence"] < min_conf:
            abstain.append(f"alacsony megbízhatóság ({e['confidence']:.0%} < {min_conf:.0%})")
        if est_m.get("top_similarity", 0) < 0.5:
            abstain.append("nincs elég hasonló összehasonlító tétel")
        if est_m.get("model") == "baseline_group_median":
            abstain.append("ehhez a piachoz csak csoportmedián becslés van (kevés piaci adat), tárgyszintű érték nincs")
        elif est_m.get("beats_baseline") is False:
            abstain.append("ezen a piacon a modell a teszten nem jobb az egyszerű alapmodellnél (kevés adat)")
        if feats.get("condition") in ("serult", "javitott"):
            abstain.append("sérült/javított tárgy: kevés ilyen tanítópélda, az érték nem becsülhető megbízhatóan")
        if listing.get("status") != "active":
            abstain.append(f"a hirdetés státusza: {listing.get('status')}")
        if not listing.get("price_huf"):
            abstain.append("nincs ár")
        base, cons = e.get("base") or {}, e.get("conservative") or {}
        hard_pre = [x for x in abstain if not x.startswith("alacsony megbízhatóság")]
        # érték alatti jelzés csak tárgyszintű, nem kizárt becslésnél
        below = (e.get("discount_pct") or 0) >= rk.get("min_discount_pct_flag", 15) and not hard_pre
        profitable = cons.get("profit_huf", -1) >= rk["min_profit_huf_to_recommend"]
        factor = 1.0
        if feats.get("condition") in ("serult", "javitott"):
            factor *= rk["damage_penalty"]
        if listing.get("sale_type") == "aukcio":
            factor *= rk["auction_uncertainty_penalty"]
        score = max(0.0, cons.get("profit_huf", 0)) * e["confidence"] * factor
        recommended = not abstain and profitable
        hard = [x for x in abstain if not x.startswith("alacsony megbízhatóság")]
        # jelölt: érték alatti és alapesetben nyereséges, de a megbízhatóság az ajánlási küszöb alatt
        candidate = (not recommended and not hard and below
                     and base.get("profit_huf", -1) >= rk["min_profit_huf_to_recommend"])
        if listing.get("sale_type") == "aukcio" and listing.get("price_huf") and e["max_bid_huf"] < listing["price_huf"]:
            recommended = False
        if (e.get("discount_pct") or 0) >= 80:
            abstain_note = "az ár a becsült érték töredéke: gyakran eltérő tárgy, alkatrész vagy hibás adat – ellenőrizd"
        else:
            abstain_note = None
        reason = explain(listing, feats, e, market, below, profitable, abstain)
        sku = est_m.get("sku") or {}
        e["p_within_10"] = est_m.get("p_within_10")
        e["precise"] = bool(est_m.get("precise"))
        e["sku"] = sku
        result["markets"][market] = {**e, "below_value": below, "profitable": profitable,
                                     "recommended": recommended, "candidate": candidate,
                                     "abstain_reasons": abstain,
                                     "score": round(score), "reason": reason,
                                     "risks": ([abstain_note] if abstain_note else []) + risks(listing, feats, est_m),
                                     "comparables": est_m.get("comparables", [])}
    return result


def _ft(v) -> str:
    return f"{v:,.0f} Ft".replace(",", " ") if v is not None else "–"


def explain(listing, feats, e, market, below, profitable, abstain) -> str:
    what = " ".join(x for x in [feats.get("brand"), (feats.get("decor") or "").split(",")[0] or None,
                                {"figurine": "figura", "vase": "váza", "plate": "tányér/tál", "tea_set": "készlet",
                                 "dinner_set": "étkészlet", "tureen": "levesestál", "bonbonniere": "bonbonier",
                                 "cup": "csésze", "teapot": "kanna/kancsó", "flower": "virág", "bowl": "tál/kaspó",
                                 "ashtray": "hamutál", "basket": "kosár", "candle": "gyertyatartó", "tile": "csempe/plakett",
                                 "small_holder": "kis tartó", "bell": "csengő", "egg": "tojás", "jewelry": "ékszer"}.get(
                                    feats.get("object_type"), "tárgy")] if x)
    mk = "magyar" if market == "HU" else "amerikai"
    parts = [f"{what}: {mk} becsült érték {_ft(e['value_huf']['q50'])} "
             f"({_ft(e['value_huf']['q10'])}–{_ft(e['value_huf']['q90'])})"]
    if e.get("discount_pct") is not None:
        parts.append(f"az ár {abs(e['discount_pct']):.0f}%-kal {'alatta' if e['discount_pct'] > 0 else 'felette'} "
                     f"van a várható eladási értéknek")
    if e.get("conservative"):
        parts.append(f"konzervatív nettó eredmény {_ft(e['conservative']['profit_huf'])}")
    if listing.get("sale_type") == "aukcio":
        parts.append(f"max. javasolt licit {_ft(e['max_bid_huf'])}")
    if abstain:
        parts.append("NINCS AJÁNLÁS: " + "; ".join(abstain))
    return "; ".join(parts) + "."
