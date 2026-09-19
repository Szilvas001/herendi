"""Transparent, conservative unit economics; not a trained price predictor.

All money is HUF. No listing-count-to-sale-time conversion is performed.
Scenario prices are assumptions, never relabelled as completed sales.
"""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Costs:
    inbound: float = 2000
    packaging: float = 2000
    outbound: float = 6000
    testing: float = 5000
    fee_rate: float = .18
    risk_rate: float = .10

    def __post_init__(self):
        values = vars(self)
        if any(not math.isfinite(v) or v < 0 for v in values.values()):
            raise ValueError("Costs must be finite and nonnegative")
        if self.fee_rate + self.risk_rate >= 1:
            raise ValueError("Fees and reserve must sum to less than 100%")


def scenario(purchase_huf, sale_huf, costs=Costs(), target_roi=.30):
    if any(not math.isfinite(v) or v < 0 for v in (purchase_huf, sale_huf, target_roi)):
        raise ValueError("Prices and ROI must be finite and nonnegative")
    overhead = costs.inbound + costs.packaging + costs.outbound + costs.testing
    capital = purchase_huf + overhead
    proceeds = sale_huf * (1 - costs.fee_rate - costs.risk_rate)
    profit = proceeds - capital
    return {
        "profit_huf": round(profit),
        "roi_pct": round(100 * profit / capital, 1) if capital else None,
        "capital_huf": round(capital),
        "max_purchase_huf": max(0, math.floor(proceeds / (1 + target_roi) - overhead)),
    }


def assessment(availability, sale_type, comparable_count, base, stress):
    """A positive hypothetical profit is only a research candidate."""
    if availability != "in_stock":
        return "Elérhetőség nem igazolt"
    if sale_type not in ("fix", "alku"):
        return "Nem rögzített beszerzési ár"
    if comparable_count < 5:
        return "Nincs elég ár-összehasonlítás"
    if base["profit_huf"] < 10000 or (base["roi_pct"] or 0) < 30 or stress["profit_huf"] <= 0:
        return "Költségekkel nem elég erős"
    return "További kutatásra; likviditás nem igazolt"
