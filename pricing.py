"""Small, explainable order-selection heuristics for the Spread dispatcher.

All probabilities here are estimates, not documented simulator probabilities.
Tune them from practice reveals and multiple seeds before relying on them.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from spread.types import PriceRequest

Lane = Tuple[str, Tuple[Tuple[str, str], ...], str]

# Central knobs, expressed in proportions or cents/minutes where appropriate.
SERVICE_TARGET = 0.95                 # leave five points of room above required 90%
MIN_ROAD_BUFFER_MINUTES = 120         # booking / access / execution uncertainty
DRIVER_FEE_SCARCITY_WEIGHT = 0.55     # uplift at maximum measured scarcity
EVENING_PRIVATE_UPLIFT = 0.15
RISK_COST_RATE = 0.35                # expected late refund / penalty exposure proxy
PORTFOLIO_RISK_WEIGHT = 0.10          # shadow cost per active order / normalized capacity
WIN_GRID = (0.85, 0.95, 1.05, 1.15, 1.25, 1.35, 1.50)
COMPETITOR_MIDPOINT = 1.40            # midpoint of documented level-8 1.26–1.54 range
PRICE_WAR_MIDPOINT = 1.12             # approximate 20% discount to usual competitor
WIN_SENSITIVITY = 0.12                # heuristic probability curve width
DECLINE_MULTIPLIER = 4                # deliberately far above public list price


def _roads(road_map: Optional[Mapping[str, Any]]) -> dict[tuple[str, str], int]:
    return {(r["from"], r["to"]): int(r["minutes"]) for r in (road_map or {}).get("roads", [])}


def estimate_regional_scarcity(request: PriceRequest, roster: Sequence[Mapping[str, Any]],
                               pending_orders: Sequence[Mapping[str, Any]]) -> float:
    """Approximate lane scarcity from available driver homes and outstanding pickups."""
    places = {leg["pickup"]["placeId"] for leg in request["legs"]}
    pool = max(1, len(roster))
    nearby = sum(1 for driver in roster if driver.get("homePlaceId") in places)
    demand = sum(1 for order in pending_orders if order.get("status") not in ("delivered", "cancelled"))
    supply_score = min(1.0, nearby / max(1.0, pool * 0.12))
    load = min(1.0, demand / max(1.0, pool * 0.08))
    return max(0.0, min(1.0, 0.65 * (1.0 - supply_score) + 0.35 * load))


def estimate_feasibility(request: PriceRequest, option: Mapping[str, Any], now: int,
                         road_map: Optional[Mapping[str, Any]], roster: Sequence[Mapping[str, Any]],
                         pending_orders: Sequence[Mapping[str, Any]]) -> tuple[bool, int, str]:
    """Return (clearly feasible, conservative minutes, reason); heuristic, not a guarantee."""
    roads = _roads(road_map)
    total = 0
    for leg in request["legs"]:
        pickup, delivery = leg["pickup"], leg["delivery"]
        drive = roads.get((pickup["placeId"], delivery["placeId"]))
        if drive is None:
            return False, 0, "road time unavailable"
        ready = pickup["window"]["from"]
        if pickup["privateAddress"] and now > pickup["window"]["to"]:
            return False, 0, "private pickup slot ended"
        if leg["car"].get("premium") and not any(d.get("rating", 0) >= 4.8 and d.get("completedGigs", 0) >= 50 for d in roster):
            return False, 0, "no experienced driver in roster"
        total += drive
        # Electric charging and the required premium/manual/plate constraints are
        # handled by dispatch after winning; where hidden facts are unknowable, add slack.
        if leg["car"].get("electric") and (leg["car"].get("chargePercent") or 100) < 30:
            total += 40
        total += max(0, ready - now)
    buffer = MIN_ROAD_BUFFER_MINUTES + (60 if len(request["legs"]) > 1 else 0)
    available = int(option["deadline"]) - now
    if available < total + buffer:
        return False, total + buffer, "insufficient deadline slack"
    return True, total + buffer, ""


def estimate_driver_cost(request: PriceRequest, road_map: Optional[Mapping[str, Any]], scarcity: float,
                         now: int) -> int:
    """Estimate fee from typical fee plus travel, scarcity and time/address premiums."""
    fee = float(request["referenceFeeCents"])
    roads = _roads(road_map)
    drive = sum(roads.get((leg["pickup"]["placeId"], leg["delivery"]["placeId"]), 0) for leg in request["legs"])
    duration_uplift = min(0.45, drive / 1800 * 0.30)
    private = any(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"] for leg in request["legs"])
    evening = now % 1440 >= 17 * 60 or now % 1440 < 7 * 60
    time_uplift = EVENING_PRIVATE_UPLIFT if private or evening else 0.0
    return max(1, int(fee * (1 + duration_uplift + DRIVER_FEE_SCARCITY_WEIGHT * scarcity + time_uplift) + 0.5))


def estimate_delivery_risk(request: PriceRequest, option: Mapping[str, Any], now: int, required_minutes: int,
                           scarcity: float, pending_orders: Sequence[Mapping[str, Any]], roster: Sequence[Mapping[str, Any]]) -> float:
    """Heuristic on-time probability, deliberately conservative and uncalibrated."""
    slack = int(option["deadline"]) - now - required_minutes
    slack_score = 1.0 / (1.0 + math.exp(-max(-20, min(20, slack / 180))))
    workload = min(1.0, len(pending_orders) / max(1.0, len(roster) * 0.08))
    chance = 0.55 + 0.43 * slack_score - 0.30 * scarcity - 0.18 * workload
    if any(leg["pickup"]["privateAddress"] for leg in request["legs"]):
        chance -= 0.08
    return max(0.05, min(0.98, chance))


def estimate_win_probability(price: int, list_price: int, level: int, now: int) -> float:
    """Approximate dealer acceptance; competitor price itself is not observable."""
    war_window = level == 8 and 8 * 60 <= now % 1440 < 18 * 60
    center = (PRICE_WAR_MIDPOINT if war_window else COMPETITOR_MIDPOINT) if level >= 7 else 1.0
    relative = price / max(1, list_price)
    return 1.0 / (1.0 + math.exp(max(-30, min(30, (relative - center) / WIN_SENSITIVITY))))


def choose_quote(request: PriceRequest, level: int, now: int, road_map: Optional[Mapping[str, Any]] = None,
                 roster: Sequence[Mapping[str, Any]] = (), pending_orders: Sequence[Mapping[str, Any]] = (),
                 trust_factor: float = 1.0) -> Dict[str, int]:
    """Select one option/price by expected contribution; {} means silence at levels 1–3."""
    if level <= 3:
        first = request["options"][0]
        feasible, minutes, _ = estimate_feasibility(request, first, now, road_map, roster, pending_orders)
        risk = estimate_delivery_risk(request, first, now, minutes, 0.5, pending_orders, roster) if feasible else 0
        return {first["kind"]: first["listPriceCents"]} if feasible and risk >= SERVICE_TARGET else {}
    scarcity = estimate_regional_scarcity(request, roster, pending_orders)
    best: Optional[tuple[float, str, int]] = None
    for option in request["options"]:
        feasible, minutes, _ = estimate_feasibility(request, option, now, road_map, roster, pending_orders)
        if not feasible:
            continue
        risk = estimate_delivery_risk(request, option, now, minutes, scarcity, pending_orders, roster)
        if risk < SERVICE_TARGET:
            continue
        cost = estimate_driver_cost(request, road_map, scarcity, now)
        portfolio = PORTFOLIO_RISK_WEIGHT * len(pending_orders) * request["referenceFeeCents"] / max(1, len(roster))
        for factor in WIN_GRID:
            price = max(1, int(option["listPriceCents"] * factor + 0.5))
            win = estimate_win_probability(price, option["listPriceCents"], level, now) * trust_factor
            win = min(0.99, win)
            contribution = price - cost - (1 - risk) * price * RISK_COST_RATE - portfolio
            value = win * contribution
            if contribution > 0 and (best is None or value > best[0]):
                best = (value, option["kind"], price)
    if best is None:
        # At levels 4–8 a high losing quote avoids the goodwill penalty for silence.
        first = request["options"][0]
        return {first["kind"]: max(first["listPriceCents"] * DECLINE_MULTIPLIER, 1_000_000)}
    return {best[1]: best[2]}


class PricingPolicy:
    """Stateful policy retaining simple win/loss learning as a modest price bias."""
    def __init__(self, level: int):
        self.level = level
        self._balance: dict[Lane, int] = {}

    def prices(self, request: PriceRequest, now: int = 0, road_map: Optional[Mapping[str, Any]] = None,
               roster: Sequence[Mapping[str, Any]] = (), pending_orders: Sequence[Mapping[str, Any]] = (),
               trust_factor: float = 1.0) -> Dict[str, int]:
        prices = choose_quote(request, self.level, now, road_map, roster, pending_orders, trust_factor)
        if not prices or self.level <= 3:
            return prices
        option, price = next(iter(prices.items()))
        key = self._key(request, option)
        bias = max(-0.05, min(0.08 if self.level < 7 else 0.12, self._balance.get(key, 0) / 100))
        prices[option] = max(1, int(price * (1 + bias) + 0.5))
        return prices

    def record_win(self, request: PriceRequest, option: str) -> None:
        key = self._key(request, option)
        self._balance[key] = min(8, self._balance.get(key, 0) + 1)

    def record_loss(self, request: PriceRequest) -> None:
        option = request["options"][0]["kind"]
        key = self._key(request, option)
        self._balance[key] = max(-5, self._balance.get(key, 0) - 1)

    @staticmethod
    def _key(request: PriceRequest, option: str) -> Lane:
        lane = tuple(sorted((leg["pickup"]["placeId"], leg["delivery"]["placeId"]) for leg in request["legs"]))
        return request["dealerId"], lane, option


def quote_prices(request: PriceRequest, level: int) -> Dict[str, int]:
    """Return initial decision without live world context (intended for simple callers/tests)."""
    return PricingPolicy(level).prices(request, now=request["arrivedAt"])
