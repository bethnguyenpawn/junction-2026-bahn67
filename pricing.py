"""Quoting. Levels 1-3 have no competitor: every quote wins the first option at its list price.

Note: a request WITHOUT a quote is declined (RULES: "Up to level 3 ... you decline by sending no
quote"), so we must still quote to win anything. Real pricing starts at level 4.

Two ways to price from level 4 (config.Params):
- flat rules: list x (quote_mult + adjustments), the presets up to `l8`;
- expected profit (`opt`): per option, the price that maximises P(win) x (price - fee - expected cost of being late),
  with both chances from logistic models fitted on our own weeks (analysis/winmodel.py, analysis/latemodel.py).
"""

from __future__ import annotations

import json
import math
import os
import zlib
from dataclasses import replace
from typing import NamedTuple

from spread.types import DeliveryOption, PriceRequest

import notes
from config import DAY, HOUR, Params

# How much dearer (+) or cheaper (-) the competitor is for cars going to each place, x list price.
# The same in every world (HANDBOOK "Dealers compare prices"); fitted from random-price quotes (analysis/lanes.py).
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lanes.json")) as _f:
    DEST_OFFSET: dict[str, float] = json.load(_f)

TRUST_CAP = 25  # RULES: each dealer counts our on-time orders up to 25, +1% accepted price each
DECLINE_MULT = 10.0  # a quote this far above list never wins and costs nothing (no quote would cost goodwill)


class Situation(NamedTuple):
    """What the desk knows about a request when it quotes."""

    km: float = 0.0  # road km of the first leg
    drive_min: int = 0  # road minutes of the first leg
    backlog: int = 0  # our won orders that still have no driver
    trust: int = 0  # the dealer's count of our on-time orders (level 8)
    near: int | None = None  # drivers living within 30 km of the pickup (None = unknown)
    near_delivery: int | None = None  # ... of the delivery place
    adapt: float = 0.0  # win-rate adjustment (Params.adapt_*)
    outage: bool = False  # the competitor looks down near the pickup (Params.outage_*)
    war: bool = False  # the competitor looks 20% cheaper today (Params.war_*)
    market: float = 0.0  # the competitor's learned level move this week + today vs a usual day, x list (market.py)
    dealer_requests: int = 0  # requests this dealer has sent this week, this one included
    partners: int = 0  # held or posted unbooked cars this car could share a driver with (Params.fit_cut)
    facts: notes.Facts | None = None  # what the note says (Params.note_reader), None = not read
    monday: bool = False


def quote(request: PriceRequest, level: int, params: Params, s: Situation = Situation()) -> dict | None:
    """The prices to quote per option. Default params: list price of the first option, as the starter."""
    first = request["options"][0]
    if level < 4:
        return {first["kind"]: first["listPriceCents"]}
    if level >= 8 and params.trust_safe_n and s.trust >= params.trust_safe_n:
        # A late order halves this dealer's trust, which is worth more wins than the order itself: be stricter.
        params = replace(
            params,
            min_slack_h=max(params.min_slack_h, params.trust_slack_h),
            decline_km=params.trust_km or params.decline_km,
        )
    if params.decline_km and s.km > params.decline_km:
        return decline(request)
    if params.max_legs and len(request["legs"]) > params.max_legs:
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
            use_flat = (params.opt_guard_backlog > 0 and s.backlog >= params.opt_guard_backlog) or (
                params.opt_guard_late > 0 and late_probability(request, option, params, s) > params.opt_guard_late
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
    return {
        o["kind"]: int(o["listPriceCents"] * mult * (1.0 if o["kind"] == "same_day" else params.later_mult) + 0.5)
        for o in options
    }


def price_flat(request: PriceRequest, option: DeliveryOption, level: int, params: Params, s: Situation) -> int:
    """Flat-rule quote for one option; guarded expected-profit pricing falls back to this exact price."""
    mult = flat_mult(request, level, params, s)
    later = 1.0 if option["kind"] == "same_day" else params.later_mult
    return int(option["listPriceCents"] * mult * later + 0.5)


def flat_mult(request: PriceRequest, level: int, params: Params, s: Situation) -> float:
    """The flat rules: quote_mult + backlog brake + adjustments for the request's situation."""
    p = params
    trade_in = bool(p.tradein_mult) and len(request["legs"]) == 2  # list price of two cars, one driver's round trip
    mult = (p.tradein_mult if trade_in else p.quote_mult) + p.backlog_k * s.backlog + s.adapt
    if p.market_k:  # follow the competitor's learned level, within limits
        mult += min(p.market_hi, max(p.market_lo, p.market_k * s.market))
    if p.explore_hi:  # research: a random price per request, to measure how the win chance falls with price
        u = zlib.crc32(request["id"].encode()) % 10000 / 10000
        mult = p.explore_lo + (p.explore_hi - p.explore_lo) * u
    if p.fit_cut and s.partners:  # likely to share a driver: cheaper for us, so win more of these
        mult -= p.fit_cut
    if p.big_n and s.dealer_requests >= p.big_n:
        mult -= p.big_cut
    if p.cost_k:  # our cost follows the typical fee; the competitor's price follows the list price
        mult += p.cost_k * (request["referenceFeeCents"] / request["options"][0]["listPriceCents"] - p.cost_mid)
    if s.monday:
        mult += p.monday_add
    if s.outage:
        mult += p.outage_add
    if s.war:
        mult -= p.war_cut
    if p.dest_k:
        mult += p.dest_k * DEST_OFFSET.get(request["legs"][0]["delivery"]["placeId"], 0.0)
    if p.private_add and private(request) and not trade_in:
        mult += p.private_add
    if s.near is not None:
        if p.dense_n and s.near >= p.dense_n:
            mult -= p.dense_cut
        if p.sparse_n and s.near < p.sparse_n:
            mult += p.sparse_add
    if level >= 8 and p.trust_w:
        mult *= 1 + p.trust_w * 0.01 * min(s.trust, TRUST_CAP)
    return mult


def best_price(request: PriceRequest, option: DeliveryOption, params: Params, s: Situation) -> int | None:
    """The price (cents) for one option with the highest expected profit, or None when no price pays.
    profit(m) = P(win | m) x (m x list x (1 - P(late) x refund share) - fee - P(late) x lost trust + trust gain)."""
    p = params
    win0 = win_base(params, s)
    dest = DEST_OFFSET.get(request["legs"][0]["delivery"]["placeId"], 0.0)
    late = late_probability(request, option, params, s)
    listed = option["listPriceCents"]
    fee = request["referenceFeeCents"] * (p.opt_fee + p.opt_backlog * s.backlog)
    lost_trust = late * p.opt_late_trust * min(s.trust, TRUST_CAP) / TRUST_CAP * listed
    gain = 0.0  # an on-time order raises the dealer's trust: more wins on its later requests
    if p.opt_trust_gain and s.trust < TRUST_CAP:
        gain = (1 - late) * p.opt_trust_gain * listed * later_requests(request, s)
    best, best_value = None, 0.0
    for k in range(round((p.opt_hi - p.opt_lo) / 0.02) + 1):
        m = p.opt_lo + 0.02 * k
        value = logistic(win0 + p.win_mult * (m - dest - s.market)) * (
            m * listed * (1 - late * p.opt_late_refund) - fee - lost_trust + gain
        )
        if value > best_value:
            best, best_value = m, value
    return None if best is None else int(best * listed + 0.5)


def late_probability(request: PriceRequest, option: DeliveryOption, params: Params, s: Situation) -> float:
    """Fitted lateness estimate used by expected-profit pricing and its reliability guard."""
    p = params
    return logistic(
        p.late_const
        + p.late_slack24 * slack(request, option, s) / DAY
        + p.late_km100 * s.km / 100
        + p.late_private * private(request)
        + p.late_near_pu * math.log1p(s.near or 0) / 4
        + p.late_near_de * math.log1p(s.near_delivery or 0) / 4
        + p.late_backlog10 * s.backlog / 10
        + p.late_hour * ((request["arrivedAt"] % DAY) >= 15 * HOUR)
    )


def win_base(params: Params, s: Situation) -> float:
    """The win model's log-odds without the price term (analysis/winmodel.py)."""
    p = params
    return (
        p.win_const
        + p.win_trust * min(s.trust, TRUST_CAP) / TRUST_CAP
        + p.win_monday * s.monday
        + p.win_dense * (s.near is not None and s.near >= 40)
        + p.win_km100 * s.km / 100
        + p.win_big * (s.dealer_requests >= 20)
    )


def relative_price(request: PriceRequest, prices: dict) -> float:
    """Our cheapest quoted option x list, minus the delivery place's offset: the price the dealer compares."""
    lists = {o["kind"]: o["listPriceCents"] for o in request["options"]}
    mult = min(price / lists[kind] for kind, price in prices.items())
    return mult - DEST_OFFSET.get(request["legs"][0]["delivery"]["placeId"], 0.0)


def later_requests(request: PriceRequest, s: Situation) -> float:
    """The requests this dealer will likely send for the rest of the week, at its rate so far (requests come Mon-Fri)."""
    days = request["arrivedAt"] / DAY
    return s.dealer_requests / max(days, 0.5) * max(0.0, 5 - days)


def slack(request: PriceRequest, option: DeliveryOption, s: Situation) -> int:
    """Minutes to spare: the option's deadline - the drive - the quote's decision time; with the note read, its
    deadline and closing time count, and a ready time later than the stated one costs the wait. A car ready N days
    after the stated day moves the won order's deadline by N days (RULES; seen in 91 of 91 such orders)."""
    if s.facts is None:
        return option["deadline"] - s.drive_min - request["respondBy"]
    stated_from = request["legs"][0]["pickup"]["window"]["from"]
    ready = s.facts.ready or 0
    wait = max(0, ready - max(request["respondBy"], stated_from))
    moved = max(0, ready // DAY - stated_from // DAY) * DAY
    return notes.due(s.facts, option["deadline"] + moved) - s.drive_min - request["respondBy"] - wait


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
