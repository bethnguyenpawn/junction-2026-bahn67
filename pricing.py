"""Quoting. Levels 1-3 have no competitor: every quote wins the first option at its list price.

Note: a request WITHOUT a quote is declined (RULES: "Up to level 3 ... you decline by sending no
quote"), so we must still quote to win anything. Real pricing starts at level 4.
"""
from __future__ import annotations

import zlib
from typing import Optional

from spread.types import PriceRequest

from config import Params


TRUST_CAP = 25  # RULES: each dealer counts our on-time orders up to 25, +1% accepted price each
DECLINE_MULT = 10.0  # a quote this far above list never wins and costs nothing (no quote would cost goodwill)


def quote(request: PriceRequest, level: int, params: Params, km: float = 0.0, backlog: int = 0, drive_min: int = 0,
          trust: int = 0, near: Optional[int] = None, adapt: float = 0.0) -> Optional[dict]:
    """The prices to quote per option, or None to send no quote. `km` = road km of the first leg,
    `backlog` = our won orders that still have no driver, `trust` = the dealer's count of our on-time orders (level 8),
    `near` = drivers living within 30 km of the pickup (None = unknown), `adapt` = the win-rate adjustment.
    Default (quote_mult=1.0, decline_km=0): list price of the first option, as the starter."""
    first = request["options"][0]
    mult = 1.0
    if level >= 4:
        mult = params.quote_mult + params.backlog_k * backlog + adapt
        if params.explore_hi:  # research: a random price per request, to measure how the win chance falls with price
            u = zlib.crc32(request["id"].encode()) % 10000 / 10000
            mult = params.explore_lo + (params.explore_hi - params.explore_lo) * u
        if params.cost_k:  # our cost follows the typical fee; the competitor's price follows the list price
            mult += params.cost_k * (request["referenceFeeCents"] / first["listPriceCents"] - params.cost_mid)
        if params.private_add and any(leg[s]["privateAddress"] for leg in request["legs"] for s in ("pickup", "delivery")):
            mult += params.private_add
        if near is not None:
            if params.dense_n and near >= params.dense_n:
                mult -= params.dense_cut
            if params.sparse_n and near < params.sparse_n:
                mult += params.sparse_add
        if level >= 8 and params.trust_w:
            mult *= 1 + params.trust_w * 0.01 * min(trust, TRUST_CAP)
        if (params.decline_km and km > params.decline_km) or mult >= DECLINE_MULT / 2:  # far, or priced out
            mult = DECLINE_MULT
    if level >= 4 and params.min_slack_h and mult < DECLINE_MULT:
        # Offer every option that leaves time to find a driver; the dealer picks. None left: decline.
        now = request["respondBy"]
        ok = [o for o in request["options"] if o["deadline"] - drive_min - now >= params.min_slack_h * 60]
        if not ok:
            return {first["kind"]: int(first["listPriceCents"] * DECLINE_MULT + 0.5)}
        return {o["kind"]: int(o["listPriceCents"] * mult * (1.0 if o["kind"] == "same_day" else params.later_mult) + 0.5)
                for o in ok}
    return {first["kind"]: int(first["listPriceCents"] * mult + 0.5)}


def is_decline(request: PriceRequest, prices: dict) -> bool:
    """True when every price is a decline (far above list), not a quote meant to win."""
    lists = {o["kind"]: o["listPriceCents"] for o in request["options"]}
    return all(price >= lists[kind] * DECLINE_MULT / 2 for kind, price in prices.items())
