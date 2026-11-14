"""Quoting. Levels 1-3 have no competitor: every quote wins the first option at its list price.

Note: a request WITHOUT a quote is declined (RULES: "Up to level 3 ... you decline by sending no
quote"), so we must still quote to win anything. Real pricing starts at level 4.

Two ways to price from level 4 (config.Params):
- flat rules: list x (quote_mult + adjustments), the presets up to `l8`;
- expected profit (`opt`): per option, the price that maximises P(win) x (price - fee - expected cost of being late),
  with both chances from logistic models fitted on our own weeks (analysis/winmodel.py, analysis/latemodel.py).
"""
from __future__ import annotations

import math
import zlib
from dataclasses import replace
from typing import NamedTuple, Optional

from spread.types import DeliveryOption, PriceRequest

from config import DAY, HOUR, Params

TRUST_CAP = 25  # RULES: each dealer counts our on-time orders up to 25, +1% accepted price each
DECLINE_MULT = 10.0  # a quote this far above list never wins and costs nothing (no quote would cost goodwill)


class Situation(NamedTuple):
    """What the desk knows about a request when it quotes."""
    km: float = 0.0                       # road km of the first leg
    drive_min: int = 0                    # road minutes of the first leg
    backlog: int = 0                      # our won orders that still have no driver
    trust: int = 0                        # the dealer's count of our on-time orders (level 8)
    near: Optional[int] = None            # drivers living within 30 km of the pickup (None = unknown)
    near_delivery: Optional[int] = None   # ... of the delivery place
    adapt: float = 0.0                    # win-rate adjustment (Params.adapt_*)
    dealer_requests: int = 0              # requests this dealer has sent this week, this one included
    monday: bool = False


def quote(request: PriceRequest, level: int, params: Params, s: Situation = Situation()) -> Optional[dict]:
    """The prices to quote per option. Default params: list price of the first option, as the starter."""
    first = request["options"][0]
    if level < 4:
        return {first["kind"]: first["listPriceCents"]}
    if level >= 8 and params.trust_safe_n and s.trust >= params.trust_safe_n:
        # A late order halves this dealer's trust, which is worth more wins than the order itself: be stricter.
        params = replace(params, min_slack_h=max(params.min_slack_h, params.trust_slack_h),
                         decline_km=params.trust_km or params.decline_km)
    if params.decline_km and s.km > params.decline_km:
        return decline(request)
    options = request["options"]
    if params.min_slack_h:  # only options that leave time to find a driver; the dealer picks among them
        options = [o for o in options if slack(request, o, s) >= params.min_slack_h * HOUR]
    elif not params.opt:
        options = [first]
    if not options:
        return decline(request)
    if params.opt:
        prices = {}
        for option in options:
            flat_price = price_flat(request, option, level, params, s)
            use_flat = (
                (params.opt_guard_backlog > 0 and s.backlog >= params.opt_guard_backlog)
                or (params.opt_guard_late > 0 and late_probability(request, option, params, s) > params.opt_guard_late)
            )
            price = flat_price if use_flat else best_price(request, option, params, s)
            guarded = params.opt_guard_late > 0 or params.opt_guard_backlog > 0 or params.opt_delta_cap > 0
            if price is None and guarded:
                price = flat_price
            if price is not None and params.opt_delta_cap > 0:
                cap = int(option["listPriceCents"] * params.opt_delta_cap + 0.5)
                price = min(flat_price + cap, max(flat_price - cap, price))
            if price is not None:
                prices[option["kind"]] = price
        return prices or decline(request)
    mult = flat_mult(request, level, params, s)
    if mult >= DECLINE_MULT / 2:  # priced out
        return decline(request)
    return {o["kind"]: int(o["listPriceCents"] * mult * (1.0 if o["kind"] == "same_day" else params.later_mult) + 0.5)
            for o in options}


def price_flat(request: PriceRequest, option: DeliveryOption, level: int, params: Params, s: Situation) -> int:
    """Flat-rule price for one option; guarded expected-profit pricing falls back to this quote."""
    mult = flat_mult(request, level, params, s)
    later = 1.0 if option["kind"] == "same_day" else params.later_mult
    return int(option["listPriceCents"] * mult * later + 0.5)


def flat_mult(request: PriceRequest, level: int, params: Params, s: Situation) -> float:
    """The flat rules: quote_mult + backlog brake + adjustments for the request's situation."""
    p = params
    mult = p.quote_mult + p.backlog_k * s.backlog + s.adapt
    if p.explore_hi:  # research: a random price per request, to measure how the win chance falls with price
        u = zlib.crc32(request["id"].encode()) % 10000 / 10000
        mult = p.explore_lo + (p.explore_hi - p.explore_lo) * u
    if p.big_n and s.dealer_requests >= p.big_n:
        mult -= p.big_cut
    if p.cost_k:  # our cost follows the typical fee; the competitor's price follows the list price
        mult += p.cost_k * (request["referenceFeeCents"] / request["options"][0]["listPriceCents"] - p.cost_mid)
    if p.private_add and private(request):
        mult += p.private_add
    if s.near is not None:
        if p.dense_n and s.near >= p.dense_n:
            mult -= p.dense_cut
        if p.sparse_n and s.near < p.sparse_n:
            mult += p.sparse_add
    if level >= 8 and p.trust_w:
        mult *= 1 + p.trust_w * 0.01 * min(s.trust, TRUST_CAP)
    return mult


def best_price(request: PriceRequest, option: DeliveryOption, params: Params, s: Situation) -> Optional[int]:
    """The price (cents) for one option with the highest expected profit, or None when no price pays.
    profit(m) = P(win | m) x (m x list x (1 - P(late) x refund share) - fee - P(late) x lost trust)."""
    p = params
    win0 = (p.win_const + p.win_trust * min(s.trust, TRUST_CAP) / TRUST_CAP + p.win_monday * s.monday
            + p.win_dense * (s.near is not None and s.near >= 40) + p.win_km100 * s.km / 100
            + p.win_big * (s.dealer_requests >= 20))
    late = late_probability(request, option, params, s)
    listed = option["listPriceCents"]
    fee = request["referenceFeeCents"] * (p.opt_fee + p.opt_backlog * s.backlog)
    lost_trust = late * p.opt_late_trust * min(s.trust, TRUST_CAP) / TRUST_CAP * listed
    best, best_value = None, 0.0
    for k in range(int(round((p.opt_hi - p.opt_lo) / 0.02)) + 1):
        m = p.opt_lo + 0.02 * k
        value = logistic(win0 + p.win_mult * m) * (m * listed * (1 - late * p.opt_late_refund) - fee - lost_trust)
        if value > best_value:
            best, best_value = m, value
    return None if best is None else int(best * listed + 0.5)


def late_probability(request: PriceRequest, option: DeliveryOption, params: Params, s: Situation) -> float:
    """Fitted lateness estimate used by expected-profit pricing and its reliability guard."""
    p = params
    return logistic(p.late_const + p.late_slack24 * slack(request, option, s) / DAY + p.late_km100 * s.km / 100
                    + p.late_private * private(request) + p.late_near_pu * math.log1p(s.near or 0) / 4
                    + p.late_near_de * math.log1p(s.near_delivery or 0) / 4 + p.late_backlog10 * s.backlog / 10
                    + p.late_hour * ((request["arrivedAt"] % DAY) >= 15 * HOUR))


def slack(request: PriceRequest, option: DeliveryOption, s: Situation) -> int:
    """Minutes to spare: the option's deadline - the drive - the quote's decision time."""
    return option["deadline"] - s.drive_min - request["respondBy"]


def private(request: PriceRequest) -> bool:
    return any(leg[stop]["privateAddress"] for leg in request["legs"] for stop in ("pickup", "delivery"))


def logistic(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def decline(request: PriceRequest) -> dict:
    """10x the list price of the first option: never wins, costs nothing."""
    first = request["options"][0]
    return {first["kind"]: int(first["listPriceCents"] * DECLINE_MULT + 0.5)}


def is_decline(request: PriceRequest, prices: dict) -> bool:
    """True when every price is a decline (far above list), not a quote meant to win."""
    lists = {o["kind"]: o["listPriceCents"] for o in request["options"]}
    return all(price >= lists[kind] * DECLINE_MULT / 2 for kind, price in prices.items())
