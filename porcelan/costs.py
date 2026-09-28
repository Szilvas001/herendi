"""Továbbértékesítési költség- és nyereségszámítás, célpiaconként.

    Becsült nettó nyereség = várható eladási bevétel − vételár − beszerzési és értékesítési költségek − adó

Minden feltételezés a settings `[fx]`, `[costs.*]` szekciójából jön, és a
kimenetben tételesen visszaadjuk (a dashboard megjeleníti). Két forgatókönyv:
  - alap: a becslési medián (q50),
  - konzervatív: a becslési intervallum alsó értéke (q10).
Aukciónál a vételár nem ismert (a licit emelkedhet): a nyereség "ha ezen az áron
nyered" feltételes érték, és kiszámoljuk a maximális javasolt licitet.
Ez nem profitígéret.
"""
from __future__ import annotations

import copy
import math

from . import settings

LARGE_TYPES = {"tureen", "dinner_set", "tea_set", "lamp", "clock", "tile"}


def assumptions(overrides: dict | None = None) -> dict:
    a = {"fx": copy.deepcopy(settings.get("fx")), "common": copy.deepcopy(settings.get("costs.common")),
         "hu": copy.deepcopy(settings.get("costs.hu")), "us": copy.deepcopy(settings.get("costs.us"))}
    for path, value in (overrides or {}).items():
        sec, _, key = path.partition(".")
        if sec in a and key in a[sec] and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
            a[sec][key] = float(value)
    return a


def is_large(features: dict) -> bool:
    size = features.get("size_cm") or 0
    pieces = features.get("pieces") or 1
    return features.get("object_type") in LARGE_TYPES or size >= 25 or pieces >= 4


def _revenue_factor(basis: str | None, a: dict) -> float:
    """Kínálati áron tanított modellnél a kínálat→eladás arány feltételezés."""
    return a["common"]["asking_to_sale_ratio"] if basis == "asking" else 1.0


def purchase_cost(listing: dict, a: dict) -> tuple[float, dict]:
    ship = listing.get("shipping_huf")
    inbound = float(ship) if ship else a["common"]["inbound_shipping_huf"]
    items = {"szállítás hozzánk": inbound, "ellenőrzés/tisztítás": a["common"]["inspection_huf"]}
    return sum(items.values()), items


def market_costs(market: str, revenue_huf: float, features: dict, a: dict) -> dict:
    if market == "HU":
        c = a["hu"]
        items = {
            "piactéri jutalék": revenue_huf * c["platform_fee_rate"],
            "fizetési díj": revenue_huf * c["payment_fee_rate"],
            "csomagolás": c["packaging_huf"],
            "kiszállítás (eladó fizeti)": c["outbound_shipping_huf"],
            "hirdetési díj": c["listing_fee_huf"],
        }
    else:
        c = a["us"]
        ship = c["intl_shipping_huf_large"] if is_large(features) else c["intl_shipping_huf_small"]
        items = {
            "eBay jutalék": revenue_huf * c["platform_fee_rate"] + c["platform_fixed_fee_usd"] * a["fx"]["huf_per_usd"],
            "fizetési díj": revenue_huf * c["payment_fee_rate"],
            "devizaváltás": revenue_huf * c["fx_conversion_rate"],
            "csomagolás (export)": c["packaging_huf"],
            "nemzetközi szállítás" + (" (nagy/készlet)" if is_large(features) else " (kis tárgy)"): ship,
            "USA vám/tarifa (DDP)": revenue_huf * c["import_duty_rate"] if c.get("duty_paid_by_seller", True) else 0.0,
        }
    items["kockázati tartalék"] = revenue_huf * a["common"]["risk_reserve_rate"]
    return items


def scenario(market: str, purchase_huf: float, sale_value_huf: float, basis: str | None, listing: dict,
             features: dict, a: dict) -> dict:
    revenue = sale_value_huf * _revenue_factor(basis, a)
    buy_extra, buy_items = purchase_cost(listing, a)
    sell_items = market_costs(market, revenue, features, a)
    costs = buy_extra + sum(sell_items.values())
    pre_tax = revenue - purchase_huf - costs
    tax = max(0.0, pre_tax) * a["common"]["profit_tax_rate"]
    profit = pre_tax - tax
    capital = purchase_huf + costs
    return {"revenue_huf": round(revenue), "purchase_huf": round(purchase_huf), "costs_huf": round(costs),
            "tax_huf": round(tax), "profit_huf": round(profit),
            "roi_pct": round(100 * profit / capital, 1) if capital > 0 else None,
            "cost_items": {k: round(v) for k, v in {**buy_items, **sell_items}.items()}}


def max_bid(market: str, sale_value_huf: float, basis, listing, features, a, min_profit: float) -> int:
    """A legmagasabb vételár, amelynél a nyereség még >= min_profit.

    A költségek nem függnek a vételártól, így a nyereség a vételárban lineáris
    (pozitív tartományban az adóval csökkentve) – zárt képlettel számolható."""
    base = scenario(market, 0.0, sale_value_huf, basis, listing, features, a)
    margin = base["revenue_huf"] - base["costs_huf"]
    tax = a["common"]["profit_tax_rate"]
    needed = min_profit / (1 - tax) if min_profit > 0 and tax < 1 else min_profit
    return int(max(0.0, margin - needed) // 100 * 100)


def evaluate(listing: dict, estimate: dict, a: dict | None = None, min_profit: float | None = None) -> dict:
    """Piaconként: érték HUF-ban, alap és konzervatív forgatókönyv, árengedmény, max licit."""
    a = a or assumptions()
    min_profit = settings.get("ranking.min_profit_huf_to_recommend") if min_profit is None else min_profit
    features = estimate.get("features", {})
    price = listing.get("price_huf")
    is_auction = listing.get("sale_type") == "aukcio"
    out = {}
    for market, est in estimate.get("markets", {}).items():
        rate = 1.0 if est["currency"] == "HUF" else a["fx"]["huf_per_usd"]
        value = {k: est[k] * rate for k in ("q10", "q50", "q90")}
        factor = _revenue_factor(est.get("basis"), a)
        res = {"value_huf": {k: round(v) for k, v in value.items()},
               "value_native": {k: round(est[k], 2) for k in ("q10", "q50", "q90")}, "currency": est["currency"],
               "expected_sale_huf": round(value["q50"] * factor), "revenue_factor": factor,
               "confidence": est["confidence"], "basis": est.get("basis"), "model": est.get("model")}
        if price:
            res["base"] = scenario(market, price, value["q50"], est.get("basis"), listing, features, a)
            res["conservative"] = scenario(market, price, value["q10"], est.get("basis"), listing, features, a)
            res["discount_pct"] = round(100 * (1 - price / (value["q50"] * factor)), 1) if value["q50"] else None
        res["max_bid_huf"] = max_bid(market, value["q10"], est.get("basis"), listing, features, a, min_profit)
        res["price_is_final"] = not is_auction
        out[market] = res
    return out
