"""Dispatch: the desk that answers each event with actions, and the driver fee schedules.

Factored out of the kit's starter (spread/starter.py) with identical behaviour at default
parameters. All fee numbers come from config.Params; `fee_schedule` and `steep_schedule`
are the decision points we tune.
"""

from __future__ import annotations

import math
import re
from collections import deque
from typing import NamedTuple

from spread.client import World
from spread.types import (
    Action,
    ActionResult,
    Audience,
    CancelledGig,
    DeskEvent,
    DeskSnapshot,
    DriverProfile,
    FeeStep,
    Gig,
    Note,
    Order,
    PostAction,
    PriceRequest,
    StopRef,
    TimeWindow,
)

import notes
import pricing
from config import DAY, HOUR, Params
from market import Market

_ROADS: dict = {}
_PLACES: dict = {}
NOTIFY_KM = 30  # RULES: the app notifies a driver of a gig whose first pickup is within 30 km of their home
WARNING_MIN = 3 * HOUR  # RULES: deadline_close comes 3 hours before lastPickupAt
STOP_MIN = {"withCharging": 40, "withPlates": 30}  # RULES: minutes a charging stop or fetching plates adds


def _load_map(client) -> None:
    """The map is the same for every world and costs no token: load it once."""
    if not _ROADS:
        m = client.map()
        _ROADS.update({(r["from"], r["to"]): r for r in m["roads"]})
        _PLACES.update({p["id"]: p for p in m["places"]})


def roads_of(client) -> dict:
    """The map's roads keyed by (from, to)."""
    _load_map(client)
    return _ROADS


def places_of(client) -> dict:
    """The map's places keyed by id, with lat and lon."""
    _load_map(client)
    return _PLACES


def straight_km(a: dict, b: dict) -> float:
    """Straight-line km between two places (the app's notification radius is a straight line)."""
    dlat = math.radians(b["lat"] - a["lat"])
    dlon = math.radians(b["lon"] - a["lon"]) * math.cos(math.radians((a["lat"] + b["lat"]) / 2))
    return 6371 * math.hypot(dlat, dlon)


def drivers_near(roster: list[DriverProfile], places: dict) -> dict[str, list[DriverProfile]]:
    """Place id -> the drivers who live within NOTIFY_KM of it. At level 8 each town keeps its own share of
    the drivers, so this says where a car is easy to move, and who lives near a delivery place."""
    homes: dict[str, list[DriverProfile]] = {}
    for driver in roster:
        homes.setdefault(driver["homePlaceId"], []).append(driver)
    return {
        pid: [d for h, ds in homes.items() if straight_km(p, places[h]) <= NOTIFY_KM for d in ds]
        for pid, p in places.items()
    }


# The events that need an answer. Views and account lines arrive with the next event that needs an answer.
WAKE_ON = [
    "price_request",
    "order_won",
    "order_changed",
    "order_cancelled",
    "visit_failed",
    "gig_expired",
    "deadline_close",
]


def wake_on(params: Params) -> list[str]:
    """The events the practice loop stops at; return-trip offers also need each delivery, next-car offers each
    booking."""
    return WAKE_ON + ["delivered"] * bool(params.return_mult) + ["gig_booked"] * bool(params.next_offer_mult)


# --- fee schedules: the main decision at levels 1-2 -------------------------------------------


def fee_schedule(now: int, fee: float, level: int, p: Params, every: int = 0) -> list[FeeStep]:
    """Normal schedule: open_mult x fee, then +raise_per_step x fee every raise_every_min (or `every`). Level 1: one
    step. With night_hold the minutes count only while drivers read (07-23), so a gig posted at night opens the day
    at its first fee instead of a fee raised for nobody."""
    steps = 1 if level == 1 else p.raise_steps
    every = every or p.raise_every_min
    return [
        {
            "at": reading_minutes_after(now, k * every) if p.night_hold and k else now + k * every,
            "feeCents": max(1, int(fee * (p.open_mult + k * p.raise_per_step) + 0.5)),
        }
        for k in range(steps)
    ]


READ_FROM, READ_TO = 7 * HOUR, 23 * HOUR  # no driver reads a notification from 23:00 to 07:00 (HANDBOOK)


def reading_minutes_after(t: int, minutes: int) -> int:
    """The world minute when `minutes` of drivers' reading time (07:00-23:00) have passed since t."""
    while True:
        day = t // DAY * DAY
        t = max(t, day + READ_FROM)
        if t >= day + READ_TO:
            t = day + DAY + READ_FROM
            continue
        if t + minutes <= day + READ_TO:
            return t + minutes
        minutes -= day + READ_TO - t
        t = day + DAY + READ_FROM


def steep_schedule(now: int, fee: float, level: int, p: Params) -> list[FeeStep]:
    """After deadline_close: steep_open_mult x fee, then +steep_raise_per_step every steep_every_min. Level 1: one step."""
    steps = 1 if level == 1 else p.steep_steps
    return [
        {
            "at": now + k * p.steep_every_min,
            "feeCents": max(1, int(fee * (p.steep_open_mult + k * p.steep_raise_per_step) + 0.5)),
        }
        for k in range(steps)
    ]


class Retry(NamedTuple):
    """How to post a leg again after a failed visit."""

    pickup_from: int = 0
    manual_licence: bool = False
    plates: bool = False


def maximum_cardinality_matching(adjacency: list[list[int]]) -> list[tuple[int, int]]:
    """Return a maximum set of disjoint edges in an undirected graph (Edmonds blossom).

    The input neighbor order is retained for deterministic tie-breaking between equally large
    matchings. Invalid indexes and self-edges are ignored.
    """
    n = len(adjacency)
    graph: list[list[int]] = [[] for _ in range(n)]
    for v, neighbors in enumerate(adjacency):
        for u in neighbors:
            if not 0 <= u < n or u == v:
                continue
            if u not in graph[v]:
                graph[v].append(u)
            if v not in graph[u]:
                graph[u].append(v)

    match = [-1] * n

    def lowest_common_ancestor(a: int, b: int, parent: list[int], base: list[int]) -> int:
        path = [False] * n
        while True:
            a = base[a]
            path[a] = True
            if match[a] == -1:
                break
            a = parent[match[a]]
        while True:
            b = base[b]
            if path[b]:
                return b
            b = parent[match[b]]

    def mark_blossom_path(
        v: int,
        blossom_base: int,
        child: int,
        blossom: list[bool],
        parent: list[int],
        base: list[int],
    ) -> None:
        while base[v] != blossom_base:
            mate = match[v]
            if mate == -1:
                return
            blossom[base[v]] = True
            blossom[base[mate]] = True
            parent[v] = child
            child = mate
            v = parent[mate]

    def augment_from(root: int) -> bool:
        parent = [-1] * n
        base = list(range(n))
        used = [False] * n
        queue = deque([root])
        used[root] = True
        endpoint = -1

        while queue and endpoint == -1:
            v = queue.popleft()
            for u in graph[v]:
                if base[v] == base[u] or match[v] == u:
                    continue
                if u == root or (match[u] != -1 and parent[match[u]] != -1):
                    blossom_base = lowest_common_ancestor(v, u, parent, base)
                    blossom = [False] * n
                    mark_blossom_path(v, blossom_base, u, blossom, parent, base)
                    mark_blossom_path(u, blossom_base, v, blossom, parent, base)
                    for i in range(n):
                        if blossom[base[i]]:
                            base[i] = blossom_base
                            if not used[i]:
                                used[i] = True
                                queue.append(i)
                elif parent[u] == -1:
                    parent[u] = v
                    if match[u] == -1:
                        endpoint = u
                        break
                    mate = match[u]
                    used[mate] = True
                    queue.append(mate)

        if endpoint == -1:
            return False
        v = endpoint
        while v != -1:
            previous = parent[v]
            next_v = match[previous] if previous != -1 else -1
            match[v] = previous
            if previous != -1:
                match[previous] = v
            v = next_v
        return True

    for root in range(n):
        if match[root] == -1:
            augment_from(root)
    return [(v, mate) for v, mate in enumerate(match) if v < mate]


class Desk:
    """What we remember, and our answer to each event. Answers wait in the outbox until sent;
    the world applies them at the current minute."""

    def __init__(
        self,
        world: World,
        level: int,
        now: int,
        params: Params,
        roads: dict | None = None,
        near: dict[str, list[DriverProfile]] | None = None,
    ):
        self.world, self.level, self.now, self.p = world, level, now, params
        self.roads = roads or {}  # (from place, to place) -> {"km", "minutes"}
        self.near = near or {}  # place id -> drivers living within 30 km (empty = not loaded)
        self.drivers = {d["id"]: d for ds in self.near.values() for d in ds}  # driver id -> profile
        self.driver_of: dict[str, str] = {}  # gig id -> the driver who booked it
        self.offers_open: dict[str, list[int]] = {}  # gig id -> minutes we sent direct offers for it
        self.adapt = 0.0  # price adjustment steered by our recent win rate (Params.adapt_*)
        self.priced: set[str] = set()  # requests we quoted to win (not declined)
        self.market = Market()  # the competitor's level this week and today, learned from our answers
        self.quoted: dict[str, tuple[int, float, float]] = {}  # request id -> (arrived, price - dest, trust share)
        self.facts_of: dict[str, notes.Facts] = {}  # order id -> what its note says (Params.note_reader)
        self.answers: list[tuple[int, str, bool]] = []  # (arrived at, pickup place, won) of answered real quotes
        self.dealer_requests: dict[str, int] = {}  # dealer id -> price requests seen this week
        self.last_seen: dict[str, int] = {}  # driver id -> minute they last viewed one of our gigs
        self.offers_sent: dict[tuple[str, int], int] = {}  # (driver id, day) -> direct offers sent
        self.outbox: list[Action] = []
        self.requests: dict[str, PriceRequest] = {}
        self.orders: dict[str, Order] = {}  # won and not cancelled
        self.leg_gigs: dict[str, dict[int, str]] = {}  # order id -> leg -> gig carrying the leg
        self.booked: set[str] = set()  # gigs a driver holds now
        self.posts: dict[str, PostAction] = {}  # gig id -> the post that made it
        self.urgent: set[str] = set()  # orders whose deadline warning has come
        self.trust: dict[str, int] = {}  # dealer id -> our on-time orders it counts (level 8 dealer trust)
        self.trust_state: dict[str, str] = {}  # order id -> "counted" | "late"
        self.first_posted: dict[str, int] = {}  # order id -> minute its first gig was posted
        self.posted_at: dict[str, int] = {}  # gig id -> minute we posted it
        self.held: dict[str, None] = {}  # won orders not posted yet, waiting for the next plan (Params.plan_every_h)
        self.next_plan = 0  # minute of the next batch plan

    def rejoin(self, snapshot: DeskSnapshot, history: list[DeskEvent]) -> None:
        """Rebuilds state from the world after a restart, then answers what was missed."""
        posted: dict[str, list[Gig]] = {}
        self.booked = {gig["id"] for gig in snapshot["gigs"] if gig["status"] in ("booked", "working", "done")}
        for gig in snapshot["gigs"]:
            posted.setdefault(gig["stops"][0]["orderId"], []).append(gig)
            if gig["status"] in ("open", "booked", "working"):
                self.carry(
                    {
                        "type": "post",
                        "stops": gig["stops"],
                        "audience": gig["audience"],
                        "schedule": gig["schedule"],
                    },
                    gig["id"],
                )
        self.requests = {e["request"]["id"]: e["request"] for e in history if e["kind"] == "price_request"}
        self.urgent = {e["orderId"] for e in history if e["kind"] == "deadline_close"}
        self.orders = {
            o["id"]: o for o in snapshot["orders"] if o["id"] in self.requests and o["status"] != "cancelled"
        }
        for order in self.orders.values():
            if order["status"] == "waiting" and not self.gigs_of(order["id"]):
                self.post(order, undelivered(order))
        for event in history:
            order = self.orders.get(event.get("orderId", ""))
            if order is None:
                continue
            if event["kind"] == "visit_failed" and order["deliveredAt"][event["leg"]] is None:
                later = [
                    g for g in posted.get(order["id"], []) if g["postedAt"] >= event["at"] and g["id"] != event["gigId"]
                ]
                if not any(stop["leg"] == event["leg"] for gig in later for stop in gig["stops"]):
                    self.retry(order["id"], event["leg"], event["reason"])
        for event in history:
            if event["kind"] == "ledger":
                self.on_ledger(event["line"])
        for request in snapshot["openRequests"]:
            self.quote(request)

    def handle(self, event: DeskEvent) -> None:
        kind = event["kind"]
        if kind == "price_request":
            self.quote(event["request"])
        elif kind == "order_won":
            self.learn(event["order"]["id"], won=True)
            self.win(event["order"])
        elif kind == "order_lost":
            self.learn(event["requestId"], won=False)
        elif kind == "order_changed":
            self.change(event["order"])
        elif kind == "order_cancelled":
            self.cancel(event["orderId"], event["gigs"])
        elif kind == "visit_failed":
            self.retry(event["orderId"], event["leg"], event["reason"])
        elif kind == "gig_expired":
            self.repost(event["gigId"])
        elif kind == "deadline_close":
            self.raise_fees(event["orderId"])
        elif kind == "gig_booked":
            self.booked.add(event["gigId"])
            self.driver_of[event["gigId"]] = event["driverId"]
            self.offer_next(event["gigId"], event["driverId"])
        elif kind in ("gig_dropped", "no_show"):
            self.booked.discard(event["gigId"])
        elif kind == "delivered":
            self.delivered(event["orderId"], event["leg"], event["at"])
            self.offer_return(event["gigId"], event["orderId"], event["leg"], event["placeId"])
        elif kind == "ledger":
            self.on_ledger(event["line"])
        elif kind == "gig_viewed":
            self.last_seen[event["driverId"]] = event["at"]
        elif kind == "offer_answered" and event["answer"] == "accepted":
            self.booked.add(event["gigId"])
            self.driver_of[event["gigId"]] = event["driverId"]

    def on_ledger(self, line: dict) -> None:
        """Dealer trust from our own account (RULES): a revenue line without a late refund is an order on
        time (+1 for its dealer, max 25); a late or undelivered order halves that dealer's count."""
        order_id = line.get("orderId")
        request = self.requests.get(order_id or "")
        if request is None:
            return
        dealer, state = request["dealerId"], self.trust_state.get(order_id)
        if line["kind"] == "revenue" and state is None:
            self.trust[dealer] = min(pricing.TRUST_CAP, self.trust.get(dealer, 0) + 1)
            self.trust_state[order_id] = "counted"
        elif line["kind"] in ("late_refund", "undelivered_penalty") and state != "late":
            count = self.trust.get(dealer, 0) - (1 if state == "counted" else 0)
            self.trust[dealer] = max(0, count) // 2
            self.trust_state[order_id] = "late"

    def delivered(self, order_id: str, leg: int, at: int) -> None:
        self.leg_gigs.get(order_id, {}).pop(leg, None)
        if order_id in self.orders:
            self.orders[order_id]["deliveredAt"][leg] = at

    def quote(self, request: PriceRequest) -> None:
        self.requests[request["id"]] = request
        dealer = request["dealerId"]
        self.dealer_requests[dealer] = self.dealer_requests.get(dealer, 0) + 1
        leg = request["legs"][0]
        road = self.roads.get((leg["pickup"]["placeId"], leg["delivery"]["placeId"]))
        situation = pricing.Situation(
            km=road["km"] if road else 0.0,
            drive_min=road["minutes"] if road else 0,
            backlog=self.backlog(),
            trust=self.trust.get(dealer, 0),
            near=len(self.near[leg["pickup"]["placeId"]]) if self.near else None,
            near_delivery=len(self.near[leg["delivery"]["placeId"]]) if self.near else None,
            adapt=self.adapt,
            dealer_requests=self.dealer_requests[dealer],
            monday=request["arrivedAt"] // DAY == 0,
            market=self.market.move(request["arrivedAt"]) if self.p.market_k else 0.0,
            partners=self.chain_partners(request) if self.p.fit_cut else 0,
            facts=notes.read(request["note"], request["arrivedAt"]) if self.p.note_reader else None,
            outage=self.outage_near(request),
            war=self.price_war(request),
        )
        prices = pricing.quote(request, self.level, self.p, situation)
        if prices and not pricing.is_decline(request, prices):
            self.priced.add(request["id"])
            if self.p.market_k:
                self.quoted[request["id"]] = (
                    request["arrivedAt"],
                    pricing.relative_price(request, prices),
                    min(situation.trust, pricing.TRUST_CAP) / pricing.TRUST_CAP,
                )
        if prices:
            self.outbox.append({"type": "quote", "requestId": request["id"], "prices": prices})

    def learn(self, request_id: str, won: bool) -> None:
        """Learns the competitor's level from each answer to a real quote, and the win-rate steering (off)."""
        request = self.requests.get(request_id)
        if request is not None and request_id in self.priced:
            self.answers.append((request["arrivedAt"], request["legs"][0]["pickup"]["placeId"], won))
        if request_id in self.quoted:
            self.market.add(*self.quoted.pop(request_id), won)
        self.steer(request_id, won)

    def outage_near(self, request: PriceRequest) -> bool:
        """True when, today between 08 and 18, we won at least outage_rate of at least outage_n answered quotes with a
        pickup within outage_km: the competitor is likely down there and dealers pay its dearer backup."""
        p, at = self.p, request["arrivedAt"]
        if not p.outage_add or not 8 * HOUR <= at % DAY < 18 * HOUR:
            return False
        place, start = request["legs"][0]["pickup"]["placeId"], at // DAY * DAY + 8 * HOUR
        near = [
            won for arrived, pickup, won in self.answers if arrived >= start and self.km(place, pickup) <= p.outage_km
        ]
        return len(near) >= p.outage_n and sum(near) >= p.outage_rate * len(near)

    def price_war(self, request: PriceRequest) -> bool:
        """True when, today (Tue-Fri) from 08:00 to 18:00, we won less than war_rate of at least war_n answered quotes:
        the competitor's price-war day."""
        p, at = self.p, request["arrivedAt"]
        if not p.war_cut or at < DAY or not 8 * HOUR <= at % DAY < 18 * HOUR:
            return False
        today = [won for arrived, _, won in self.answers if arrived >= at // DAY * DAY + 8 * HOUR]
        return len(today) >= p.war_n and sum(today) < p.war_rate * len(today)

    def steer(self, request_id: str, won: bool) -> None:
        """Win-rate steering: each answer to a real quote moves the price a step, so that over time we win
        adapt_target of our quotes. It follows the competitor's level, its slow Mondays and its price-war day."""
        p = self.p
        if not p.adapt_target or request_id not in self.priced:
            return
        self.priced.discard(request_id)
        if won:
            self.adapt = min(p.adapt_hi, self.adapt + p.adapt_step * (1 - p.adapt_target))
        elif self.backlog_count() <= p.adapt_backlog:
            self.adapt = max(p.adapt_lo, self.adapt - p.adapt_step * p.adapt_target)

    def backlog(self) -> int:
        """Won orders with an undelivered car that no driver holds (held orders are planned, not stuck)."""
        return self.backlog_count() if self.p.backlog_k else 0

    def backlog_count(self) -> int:
        """Driverless won cars; with backlog_h only those whose last pickup is that close (a real capacity warning,
        not a car posted minutes ago or one waiting days for a chain partner)."""
        horizon = self.now + self.p.backlog_h * HOUR if self.p.backlog_h else float("inf")
        return sum(
            1
            for oid, order in self.orders.items()
            if undelivered(order)
            and oid not in self.held
            and order["lastPickupAt"] <= horizon
            and not any(g in self.booked for g in self.gigs_of(oid))
        )

    def win(self, order: Order) -> None:
        if order["id"] in self.requests and order["id"] not in self.orders:
            self.orders[order["id"]] = order
            if self.p.plan_every_h and self.holdable(order["id"]):
                self.held[order["id"]] = None
            elif not (self.p.pair_fee and self.pair(order)):
                self.post(order, undelivered(order))

    def holdable(self, order_id: str) -> bool:
        """A plain one-car order with at least hold_h hours until its latest pickup can wait for the next plan."""
        order = self.orders[order_id]
        return (
            order_id not in self.urgent
            and self.last_pickup(order) - self.now >= self.p.hold_h * HOUR
            and self.single_stops(order_id) is not None
        )

    def plan(self) -> None:
        """Batch plan: pairs the held cars into two-car gigs (round trips first, then the shortest link), and posts
        alone each held car that can no longer wait for the next plan."""
        p = self.p
        self.next_plan = next_plan_at(self.now, p.plan_every_h)
        stops_of = {oid: self.single_stops(oid) for oid in self.held if oid in self.orders}
        held = {oid: stops for oid, stops in stops_of.items() if stops is not None}
        paired: set[str] = self.plan_chains(held) if p.chain_max >= 2 else self.plan_pairs(held)
        for oid in list(self.held):
            order = self.orders.get(oid)
            if order is None:
                self.held.pop(oid)
            elif oid not in paired and self.last_pickup(order) - self.next_plan < (p.wait_h or p.hold_h) * HOUR:
                self.post(order, undelivered(order))

    def plan_pairs(self, held: dict[str, list[StopRef]]) -> set[str]:
        """Pairs held cars into two-car gigs, round trips first, then the shortest link (pair_match: the largest set
        of pairs). Returns the paired cars."""
        if self.p.pair_match:
            paired: set[str] = set()
            for a, b in self.match_pairs(held):
                paired |= {a, b}
                self.post_pair(held[a] + held[b], (a, b))
            return paired
        p = self.p
        options = []
        for a, first in held.items():
            for b, second in held.items():
                if a == b:
                    continue
                link = self.chain_minutes(first, second)
                if link is None:
                    continue
                home = self.km(
                    self.orders[b]["legs"][0]["delivery"]["placeId"], self.orders[a]["legs"][0]["pickup"]["placeId"]
                )
                options.append((home > p.pair_km, link, a, b, first + second))
        paired: set[str] = set()
        for _, _, a, b, stops in sorted(options, key=lambda o: o[:2]):
            if a not in paired and b not in paired:
                paired |= {a, b}
                self.post_pair(stops, (a, b))
        return paired

    def plan_chains(self, held: dict[str, list[StopRef]]) -> set[str]:
        """Chains of up to chain_max cars per driver from the held cars and the posted, unbooked one-car gigs.
        A posted car joins a chain only after its gig is withdrawn (a driver may have booked it meanwhile).
        Returns the held cars that went into a chain."""
        lone = self.unbooked_lone_gigs()
        stale = self.stale_chains() if self.p.chain_replan else {}
        freed_chains = self.withdraw_now(list(dict.fromkeys(stale.values())))
        for oid, gig_id in stale.items():
            if gig_id in freed_chains:
                self.leg_gigs.pop(oid, None)
                stops = self.single_stops(oid)
                if stops is None:  # can't join a chain any more: post it alone now
                    self.post(self.orders[oid], undelivered(self.orders[oid]))
                else:
                    lone[oid] = (gig_id, stops)
        cars = {**held, **{oid: stops for oid, (_, stops) in lone.items()}}
        wanted = [lone[oid][0] for chain in self.build_chains(cars) if len(chain) > 1 for oid in chain if oid in lone]
        freed = self.withdraw_now([g for g in dict.fromkeys(wanted) if g not in freed_chains]) | freed_chains
        for oid, (gig_id, _) in lone.items():
            if gig_id in freed:
                self.leg_gigs.pop(oid, None)
        pool = {oid: stops for oid, stops in cars.items() if oid in held or lone[oid][0] in freed}
        chained: set[str] = set()
        for chain in self.build_chains(pool):
            if len(chain) > 1:
                chained |= set(chain)
                self.post_pair([stop for oid in chain for stop in pool[oid]], tuple(chain))
            elif chain[0] not in held:  # withdrawn but its partner was booked meanwhile: post it alone again
                self.post(self.orders[chain[0]], undelivered(self.orders[chain[0]]))
        return chained & set(held)

    def stale_chains(self) -> dict[str, str]:
        """Order id -> gig of every multi-car gig no driver booked within split_after_min (chain_replan: its cars go
        back into the plan instead of being split into one-car gigs)."""
        stale = {}
        for gig_id, action in self.posts.items():
            if (
                gig_id not in self.booked
                and self.is_pair(gig_id)
                and self.now - self.posted_at.get(gig_id, self.now) >= self.p.split_after_min
                and self.is_live(gig_id)
            ):
                stale |= {stop["orderId"]: gig_id for stop in action["stops"] if stop["orderId"] in self.orders}
        return stale

    def chain_partners(self, request: PriceRequest) -> int:
        """Held or posted unbooked cars that one driver could carry before or after this request's car: such a car
        will likely share a driver and cost less (Params.fit_cut)."""
        if len(request["legs"]) > 1 or pricing.private(request):
            return 0
        leg = request["legs"][0]
        due = max(option["deadline"] for option in request["options"])
        new = (leg["pickup"]["placeId"], leg["delivery"]["placeId"], leg["pickup"]["window"]["from"], due, 0)
        others = [self.single_stops(oid) for oid in self.held if oid in self.orders]
        others += [stops for _, stops in self.unbooked_lone_gigs().values()]
        spans = [self.span(stops) for stops in others if stops is not None]
        return sum(self.link_minutes(new, s) is not None or self.link_minutes(s, new) is not None for s in spans)

    def unbooked_lone_gigs(self) -> dict[str, tuple[str, list[StopRef]]]:
        """Posted one-car gigs no driver has booked, of plain cars that are not urgent: order id -> (gig, stops)."""
        lone = {}
        for gig_id, action in self.posts.items():
            oid = action["stops"][0]["orderId"]
            if (
                gig_id not in self.booked
                and len(action["stops"]) == 2
                and oid not in self.urgent
                and self.leg_gigs.get(oid, {}).get(0) == gig_id
            ):
                stops = self.single_stops(oid)
                if stops is not None:
                    lone[oid] = (gig_id, stops)
        return lone

    def match_pairs(self, cars: dict[str, list[StopRef]]) -> list[tuple[str, str]]:
        """The largest set of disjoint feasible pairs (Edmonds' blossom matching), each in its better order (round
        trip first, then the shorter link), best first. Greedy pairing can take one pair that blocks two others."""
        ids = list(cars)
        best: dict[tuple[int, int], tuple[tuple, str, str]] = {}
        neighbors: list[list[tuple[tuple, int]]] = [[] for _ in ids]
        for i, a in enumerate(ids):
            for j in range(i + 1, len(ids)):
                b = ids[j]
                choices = []
                for first, second in ((a, b), (b, a)):
                    link = self.chain_minutes(cars[first], cars[second])
                    if link is not None:
                        home = self.km(
                            self.orders[second]["legs"][0]["delivery"]["placeId"],
                            self.orders[first]["legs"][0]["pickup"]["placeId"],
                        )
                        choices.append(((home > self.p.pair_km, link, first, second), first, second))
                if choices:
                    best[(i, j)] = min(choices)
                    neighbors[i].append((best[(i, j)][0], j))
                    neighbors[j].append((best[(i, j)][0], i))
        adjacency = [[j for _, j in sorted(row)] for row in neighbors]
        chosen = sorted(best[(min(i, j), max(i, j))] for i, j in maximum_cardinality_matching(adjacency))
        return [(first, second) for _, first, second in chosen]

    def build_chains(self, cars: dict[str, list[StopRef]]) -> list[list[str]]:
        """Greedy chaining: repeatedly joins the two chains with the best link (a round trip home first, with
        chain_home also a chain ending where many drivers live, then the shortest empty drive) while one driver can
        still do the whole chain on time (chain_fits). With chain_fresh_head a car we posted before never leads a
        chain: the app notifies drivers near a gig's first pickup, and of each order only once (RULES)."""
        p = self.p
        place = {oid: (stops[0]["orderId"], self.orders[oid]["legs"][0]) for oid, stops in cars.items()}
        links = {  # tail car -> [(link minutes, head car)] within pair_km
            a: sorted(
                (road["minutes"], b)
                for b in cars
                if b != a
                and (road := self.roads.get((place[a][1]["delivery"]["placeId"], place[b][1]["pickup"]["placeId"])))
                and road["km"] <= p.pair_km
            )
            for a in cars
        }
        chains = {oid: [oid] for oid in cars}  # head car -> chain
        tail_of = {oid: oid for oid in cars}  # head car -> its tail car
        if p.chain_match:  # start from the largest set of pairs, then grow them into longer chains
            for first, second in self.match_pairs(cars):
                chains[first] = [first, second]
                tail_of[first] = second
                del chains[second], tail_of[second]
        while True:
            best = None
            for head, chain in chains.items():
                if p.chain_fresh_head and head in self.first_posted:
                    continue  # its drivers heard of it already: a chain led by it would notify nobody
                for minutes, nxt in links[tail_of[head]]:
                    if nxt not in chains or nxt == head or len(chain) + len(chains[nxt]) > p.chain_max:
                        continue
                    joined = chain + chains[nxt]
                    if not self.chain_fits([cars[oid] for oid in joined]):
                        continue
                    end = place[joined[-1]][1]["delivery"]["placeId"]
                    home = self.km(end, place[head][1]["pickup"]["placeId"]) <= p.pair_km  # a round trip
                    if p.chain_home:  # or it ends where many drivers live: one of them takes it to go home
                        home = home or len(self.near.get(end, [])) >= p.home_n
                    key = (not home, minutes)
                    if best is None or key < best[0]:
                        best = (key, head, nxt)
            if best is None:
                return list(chains.values())
            _, head, nxt = best
            chains[head] += chains.pop(nxt)
            tail_of[head] = tail_of.pop(nxt)

    def chain_fits(self, cars: list[list[StopRef]]) -> bool:
        """One driver starting pair_lead_min from now delivers every car pair_margin_h before its deadline, within
        12 h of work."""
        margin = self.p.pair_margin_h * HOUR
        t = start = None
        previous = None
        for stops in cars:
            pickup, delivery, ready, due, extra = self.span(stops)
            pickup_to, delivery_from = self.slot_limits(stops)
            drive = self.roads.get((pickup, delivery))
            if drive is None:
                return False
            if previous is None:
                t = start = max(self.now + self.p.pair_lead_min, ready)
            else:
                link = self.roads.get((previous, pickup))
                if link is None:
                    return False
                t = max(t + link["minutes"], ready)
            if t > pickup_to:
                return False
            t = max(t + drive["minutes"] + extra, delivery_from)
            if t > due - margin or t - start > 12 * HOUR:
                return False
            previous = delivery
        return True

    def span(self, stops: list[StopRef]) -> tuple[str, str, int, int, int]:
        """A one-car gig's pickup place, delivery place, earliest pickup, latest delivery and extra stop minutes."""
        order = self.orders[stops[0]["orderId"]]
        leg = order["legs"][0]
        ready = stops[0].get("window", leg["pickup"]["window"])["from"]
        due = min(order["deadline"], stops[1].get("window", {"to": order["deadline"]})["to"])
        extra = sum(minutes for flag, minutes in STOP_MIN.items() if stops[0].get(flag))
        return leg["pickup"]["placeId"], leg["delivery"]["placeId"], ready, due, extra

    def slot_limits(self, stops: list[StopRef]) -> tuple[float, float]:
        """The latest pickup and the earliest delivery a one-car gig allows (a private address's booked slot)."""
        leg = self.orders[stops[0]["orderId"]]["legs"][0]
        pickup_to = stops[0].get("window", leg["pickup"]["window"])["to"]
        delivery_from = stops[1].get("window", leg["delivery"]["window"])["from"]
        return pickup_to, delivery_from

    def withdraw_now(self, gig_ids: list[str]) -> set[str]:
        """Withdraws gigs at once and returns those withdrawn (a gig a driver booked meanwhile stays)."""
        if not gig_ids:
            return set()
        self.send()
        freed = set()
        for i in range(0, len(gig_ids), 50):
            batch = gig_ids[i : i + 50]
            results = self.world.act([{"type": "withdraw", "gigId": gig_id} for gig_id in batch])
            freed |= {gig_id for gig_id, result in zip(batch, results) if result["ok"] is True}
        return freed

    def post_pair(self, stops: list[StopRef], order_ids: tuple[str, ...]) -> None:
        """One gig for several one-car orders, at fees_for (pair_fee x their typical fees)."""
        for oid in order_ids:
            self.held.pop(oid, None)
            self.first_posted.setdefault(oid, self.now)
        premium = any(leg["car"]["premium"] for oid in order_ids for leg in self.orders[oid]["legs"])
        self.outbox.append(
            {
                "type": "post",
                "stops": stops,
                "audience": {"experienced": premium, "manualLicence": self.manual(order_ids)},
                "schedule": self.fees_for(stops),
            }
        )

    def stops_for(self, order: Order, legs: list[int], note: Note | None, retry: Retry) -> list[StopRef]:
        """stops_for with what the desk knows: the note's facts, the clock and the road distances."""
        return stops_for(order, legs, note, retry, self.facts(order["id"]), self.now, self.p.charge_km, self.roads)

    def facts(self, order_id: str) -> notes.Facts | None:
        """What the order's note says (Params.note_reader), read once; None = the starter's reader."""
        if not self.p.note_reader:
            return None
        if order_id not in self.facts_of:
            request = self.requests[order_id]
            self.facts_of[order_id] = notes.read(request["note"], request["arrivedAt"])
        return self.facts_of[order_id]

    def last_pickup(self, order: Order) -> int:
        """The world's latest pickup, moved earlier by as much as the note's deadline or the delivery site's real
        closing time is earlier than the option's deadline (the world counts only the option's)."""
        facts = self.facts(order["id"])
        if facts is None:
            return order["lastPickupAt"]
        return order["lastPickupAt"] - (order["deadline"] - min(order["deadline"], notes.due(facts, order["deadline"])))

    def manual(self, order_ids) -> bool:
        """Whether a note says one of these cars has a manual gearbox (the driver needs that licence)."""
        return any((facts := self.facts(oid)) is not None and facts.manual for oid in order_ids)

    def wake_at(self) -> float:
        """The next minute the desk wants to act without an event: the ladder's tick or the next plan."""
        at = float("inf")
        if self.p.ladder_per_hour > 0:
            at = self.now + self.p.tick_min
        if self.p.plan_every_h:
            at = min(at, max(self.next_plan, self.now + 1))
        if self.p.split_after_min:
            at = min(at, self.now + 30)  # check for unbooked pairs every half hour
        return at

    def pair(self, order: Order) -> bool:
        """Puts a new one-car order in one gig with a waiting one-car gig, when one driver can deliver both
        on time: the first car ends near the second's pickup. Withdraws the waiting gig. False = no partner."""
        new = self.single_stops(order["id"])
        if new is None:
            return False
        best = None
        for gig_id, action in self.posts.items():
            other = action["stops"][0]["orderId"]
            if (
                gig_id in self.booked
                or len(action["stops"]) != 2
                or other in self.urgent
                or self.leg_gigs.get(other, {}).get(0) != gig_id
                or self.single_stops(other) is None
            ):
                continue
            for first, second in ((action["stops"], new), (new, action["stops"])):
                link = self.chain_minutes(first, second)
                if link is not None and (best is None or link < best[0]):
                    best = (link, gig_id, first + second)
        if best is None:
            return False
        _, gig_id, stops = best
        other = self.posts[gig_id]["stops"][0]["orderId"]
        self.outbox.append({"type": "withdraw", "gigId": gig_id})
        self.leg_gigs.pop(other, None)
        self.first_posted.setdefault(order["id"], self.now)
        premium = any(leg["car"]["premium"] for oid in (order["id"], other) for leg in self.orders[oid]["legs"])
        self.outbox.append(
            {
                "type": "post",
                "stops": stops,
                "audience": {"experienced": premium, "manualLicence": self.manual((order["id"], other))},
                "schedule": self.fees_for(stops),
            }
        )
        return True

    def single_stops(self, order_id: str) -> list[StopRef] | None:
        """The stops of a one-car order that can share a driver (private addresses only with chain_private, charging
        stops only with chain_charging), else None."""
        order = self.orders.get(order_id)
        if order is None or len(order["legs"]) != 1 or undelivered(order) != [0]:
            return None
        leg = order["legs"][0]
        if (leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]) and not self.p.chain_private:
            return None
        note = self.requests[order_id]["note"]
        stops = without_windows(self.stops_for(order, [0], note, Retry()), self.now)
        return None if stops[0].get("withCharging") and not self.p.chain_charging else stops

    def chain_minutes(self, first: list[StopRef], second: list[StopRef]) -> int | None:
        """Road minutes from the first car's delivery to the second car's pickup, when one driver starting
        pair_lead_min from now delivers both pair_margin_h before their deadlines within 12 h of driving."""
        return self.link_minutes(self.span(first), self.span(second))

    def link_minutes(self, first: tuple, second: tuple) -> int | None:
        """chain_minutes for two spans (pickup place, delivery place, earliest pickup, latest delivery, stop minutes)."""
        p1, d1, ready1, due1, extra1 = first
        p2, d2, ready2, due2, extra2 = second
        link = self.roads.get((d1, p2))
        drive1, drive2 = self.roads.get((p1, d1)), self.roads.get((p2, d2))
        if not (link and drive1 and drive2) or link["km"] > self.p.pair_km:
            return None
        if drive1["minutes"] + link["minutes"] + drive2["minutes"] > 12 * HOUR:
            return None
        margin = self.p.pair_margin_h * HOUR
        start = max(self.now + self.p.pair_lead_min, ready1)
        at1 = start + drive1["minutes"] + extra1
        at2 = max(at1 + link["minutes"], ready2) + drive2["minutes"] + extra2
        if at1 > due1 - margin or at2 > due2 - margin or at2 - start > 12 * HOUR:
            return None
        return link["minutes"]

    def cancel(self, order_id: str, gigs: list[CancelledGig]) -> None:
        """Forgets a cancelled order. A gig the world withdrew for it may carry other cars: RULES say to post them
        again, else they keep no gig and are never delivered."""
        for books in (self.orders, self.leg_gigs, self.held):
            books.pop(order_id, None)
        for gig in gigs:
            action = self.posts.get(gig["gigId"])
            if gig["outcome"] != "withdrawn" or action is None:
                continue
            for other in dict.fromkeys(stop["orderId"] for stop in action["stops"]):
                legs = self.leg_gigs.get(other, {})
                freed = [leg for leg, gig_id in legs.items() if gig_id == gig["gigId"]]
                for leg in freed:
                    legs.pop(leg)
                if freed and other in self.orders:
                    self.post(self.orders[other], freed)

    def change(self, order: Order) -> None:
        if order["id"] in self.orders:
            self.orders[order["id"]] = order
            if self.withdraw(order["id"]):
                self.post(order, undelivered(order))

    def repost(self, gig_id: str) -> None:
        """Posts a gig again when one of its windows ended before a driver booked it."""
        action = self.posts.get(gig_id)
        if action is None or not any(
            self.leg_gigs.get(s["orderId"], {}).get(s["leg"]) == gig_id for s in action["stops"]
        ):
            return
        for stop in action["stops"]:
            self.leg_gigs.get(stop["orderId"], {}).pop(stop["leg"], None)
        order = self.orders.get(action["stops"][0]["orderId"])
        if order is None:
            return
        stops = without_windows([s for s in action["stops"] if s["orderId"] in self.orders], float("inf"))
        self.outbox.append(
            {
                **action,
                "stops": stops,
                "schedule": self.fees_for(stops),
            }
        )

    def raise_fees(self, order_id: str) -> None:
        """From the order's deadline warning on, its unbooked gigs go at the steep fees."""
        order = self.orders.get(order_id)
        if order is None:
            return
        self.urgent.add(order_id)
        if order_id in self.held:  # held for a plan: post it now, at the steep fees
            self.post(order, undelivered(order))
            return
        self.send_post_of(order_id)
        for gig_id in self.gigs_of(order_id):
            if gig_id not in self.booked and self.p.split_after_min and self.is_pair(gig_id):
                self.split(gig_id)  # a pair whose car is now urgent: one gig per car, at the steep fees
            elif gig_id not in self.booked:
                new = self.fees_for(self.posts[gig_id]["stops"])
                self.outbox.append({"type": "reprice", "gigId": gig_id, "schedule": new})
                self.posts[gig_id] = {**self.posts[gig_id], "schedule": new}

    def fees_for(self, stops: list[StopRef]) -> list[FeeStep]:
        """The fee schedule of a gig: the typical fee of each car it carries; steep once any order is urgent."""
        order_ids = list(dict.fromkeys(stop["orderId"] for stop in stops))
        fee = sum(
            self.typical_fee(stop["orderId"]) / len(self.requests[stop["orderId"]]["legs"])
            for stop in stops
            if stop["kind"] == "pickup"
        )
        if len(order_ids) > 1:  # one driver, one trip there and one home for all cars
            fee *= self.p.pair_fee - self.p.chain_fee_step * (len(order_ids) - 2)
        if any(order_id in self.urgent for order_id in order_ids):
            return steep_schedule(self.now, fee, self.level, self.p)
        fee *= self.home_factor(stops[-1])
        order = self.orders.get(order_ids[0])
        if order is not None:
            fee *= self.ease(order)
        if self.p.ladder_per_hour > 0:
            return [
                {
                    "at": self.now,
                    "feeCents": max(1, int(fee * self.ladder_mult(order_ids[0]) + 0.5)),
                }
            ]
        return fee_schedule(self.now, fee, self.level, self.p, self.raise_every(order_ids))

    def raise_every(self, order_ids: list[str]) -> int:
        """Minutes between raises: slow_every_min when every car still has slow_after_h hours until its last pickup
        (no hurry, so drivers who wait for a raise wait long); 0 = the usual raise_every_min."""
        p = self.p
        if not p.slow_every_min:
            return 0
        horizon = self.now + p.slow_after_h * HOUR
        orders = [self.orders.get(oid) for oid in order_ids]
        return p.slow_every_min if all(o is not None and self.last_pickup(o) >= horizon for o in orders) else 0

    def typical_fee(self, order_id: str) -> float:
        return pricing.typical_fee(self.requests[order_id], self.p)

    def home_factor(self, last: StopRef) -> float:
        """Fee factor for a gig that ends where many drivers live (Params.home_n): one of them nearly always takes
        it, at our first fee, because their trip home is free (Exp. 47). 1.0 = off."""
        p, order = self.p, self.orders.get(last["orderId"])
        if p.home_fee == 1.0 or not self.near or order is None:
            return 1.0
        place = order["legs"][last["leg"]]["delivery"]["placeId"]
        return p.home_fee if len(self.near.get(place, [])) >= p.home_n else 1.0

    def ease(self, order: Order) -> float:
        """Fee factor for how easy the car is to move: many drivers near the pickup (they hear of the gig and
        pay little to reach it), or many hours left before the last pickup (time to raise slowly). 1.0 = off."""
        p, factor = self.p, 1.0
        pickup = order["legs"][undelivered(order)[0] if undelivered(order) else 0]["pickup"]["placeId"]
        if p.dense_fee != 1.0 and self.near and len(self.near[pickup]) >= p.dense_n:
            factor *= p.dense_fee
        if p.slack_fee != 1.0 and order["lastPickupAt"] - self.now >= p.slack_fee_h * HOUR:
            factor *= p.slack_fee
        if p.trust_fee != 1.0 and self.trust.get(self.requests[order["id"]]["dealerId"], 0) >= p.trust_fee_n:
            factor *= p.trust_fee
        return factor

    def ladder_mult(self, order_id: str) -> float:
        hours = (self.now - self.first_posted.get(order_id, self.now)) / HOUR
        return min(self.p.ladder_cap, self.p.open_mult + self.p.ladder_per_hour * hours)

    def tick(self) -> None:
        """Runs the batch plan when due, and raises the fee of every unbooked, non-urgent gig to the ladder's target."""
        if self.p.plan_every_h and self.now >= self.next_plan:
            self.plan()
        if self.p.split_after_min and not (self.p.chain_max >= 2 and self.p.chain_replan):
            self.split_stale_pairs()
        if self.p.note_reader:  # the world warns by the option's deadline; a note's earlier one needs our own warning
            for order_id, order in list(self.orders.items()):
                due_soon = self.last_pickup(order) - WARNING_MIN <= self.now < order["lastPickupAt"] - WARNING_MIN
                if due_soon and order_id not in self.urgent and undelivered(order):
                    self.raise_fees(order_id)
        if self.p.ladder_per_hour <= 0:
            return
        for order_id in list(self.orders):
            if order_id in self.urgent:
                continue
            for gig_id in self.gigs_of(order_id):
                if gig_id in self.booked or gig_id not in self.posts:
                    continue
                post = self.posts[gig_id]
                new = self.fees_for(post["stops"])
                if new[-1]["feeCents"] > post["schedule"][-1]["feeCents"]:
                    self.outbox.append({"type": "reprice", "gigId": gig_id, "schedule": new})
                    self.posts[gig_id] = {**post, "schedule": new}

    def retry(self, order_id: str, leg: int, reason: str) -> None:
        if order_id in self.orders:
            order = self.orders[order_id]
            self.leg_gigs.get(order_id, {}).pop(leg, None)
            car_not_there = reason in ("not_ready", "closed")
            pickup_from = retry_from(order, self.requests[order_id], leg, self.now) if car_not_there else 0
            self.post(
                order,
                [leg],
                Retry(
                    pickup_from,
                    manual_licence=reason == "licence",
                    plates=reason == "no_plates",
                ),
            )

    def post(self, order: Order, legs: list[int], retry: Retry = Retry()) -> None:  # noqa: B008 - immutable
        # A premium car needs an experienced driver: the fine is €150 a car.
        audience: Audience = {
            "experienced": any(leg["car"]["premium"] for leg in order["legs"]),
            "manualLicence": retry.manual_licence or self.manual([order["id"]]),
        }
        note = self.requests[order["id"]]["note"]
        stops = without_windows(self.stops_for(order, legs, note, retry), self.now)
        self.held.pop(order["id"], None)
        self.first_posted.setdefault(order["id"], self.now)
        self.outbox.append(
            {
                "type": "post",
                "stops": stops,
                "audience": audience,
                "schedule": self.fees_for(stops),
            }
        )
        if len(legs) == 1:
            return
        # A trade-in over the 12-hour limit for a two-car gig goes as one gig per car.
        self.send()
        if not self.gigs_of(order["id"]):
            for leg in legs:
                self.post(order, [leg], retry)

    def gigs_of(self, order_id: str) -> list[str]:
        return list(dict.fromkeys(self.leg_gigs.get(order_id, {}).values()))

    def carry(self, action: PostAction, gig_id: str) -> None:
        for stop in action["stops"]:
            self.leg_gigs.setdefault(stop["orderId"], {})[stop["leg"]] = gig_id
        self.posts[gig_id] = action
        self.posted_at[gig_id] = self.now

    def split(self, gig_id: str) -> None:
        """Withdraws an unbooked two-car gig and posts each car alone: a pair must never leave two cars without
        a driver."""
        order_ids = list(dict.fromkeys(stop["orderId"] for stop in self.posts[gig_id]["stops"]))
        self.send()  # the withdraw goes alone, so we know whether it worked
        if self.world.act([{"type": "withdraw", "gigId": gig_id}])[0]["ok"] is not True:
            return  # a driver booked it meanwhile: keep the pair
        for oid in order_ids:
            self.leg_gigs.pop(oid, None)
        for oid in order_ids:
            if oid in self.orders:
                self.post(self.orders[oid], undelivered(self.orders[oid]))

    def split_stale_pairs(self) -> None:
        """Splits every two-car gig that no driver booked within split_after_min."""
        for gig_id, action in list(self.posts.items()):
            if (
                gig_id not in self.booked
                and self.is_pair(gig_id)
                and self.now - self.posted_at.get(gig_id, self.now) >= self.p.split_after_min
                and self.is_live(gig_id)
            ):
                self.split(gig_id)

    def withdraw(self, order_id: str) -> bool:
        """Withdraws an order's gigs. False, and nothing withdrawn, when a driver holds one. The other car of a
        withdrawn two-car gig is posted again alone (test final: without this it was never posted again)."""
        self.send_post_of(order_id)
        gigs = self.gigs_of(order_id)
        if any(gig_id in self.booked for gig_id in gigs):
            return False
        partners = {stop["orderId"] for gig_id in gigs for stop in self.posts[gig_id]["stops"]} - {order_id}
        for oid in (order_id, *partners):
            self.leg_gigs.pop(oid, None)
        self.outbox += [{"type": "withdraw", "gigId": gig_id} for gig_id in gigs]
        for oid in partners:
            if oid in self.orders:
                self.post(self.orders[oid], undelivered(self.orders[oid]))
        return True

    def send_post_of(self, order_id: str) -> None:
        if any(action["type"] == "post" and action["stops"][0]["orderId"] == order_id for action in self.outbox):
            self.send()

    def send(self) -> None:
        actions, self.outbox = self.outbox, []
        if actions:
            self.read_results(actions, self.world.act(actions))

    def read_results(self, actions: list[Action], results: list[ActionResult]) -> None:
        for action, result in zip(actions, results):
            if action["type"] == "post" and result["ok"] is True:
                self.carry(action, result["id"])
                self.offer(action, result["id"])

    def offer(self, action: PostAction, gig_id: str) -> None:
        """Direct offers below the app's fee to drivers who live near the delivery place: the app does not
        notify them, and the trip home costs them nothing (HANDBOOK). Off by default: in tests almost all
        offers went unread or were declined (LESSONS.md, Experiment 18)."""
        order_id = action["stops"][0]["orderId"]
        order = self.orders.get(order_id)
        if not self.p.offer_mult or not self.near or order is None or order_id in self.urgent:
            return
        last = next(s for s in reversed(action["stops"]) if s["kind"] == "delivery")
        place = order["legs"][last["leg"]]["delivery"]["placeId"]
        audience, day = action["audience"], self.now // DAY
        fits = [
            d
            for d in self.near.get(place, [])
            if self.fits(d, audience) and self.offers_sent.get((d["id"], day), 0) < 3
        ]
        # Drivers who looked at our gigs today work today; the rest read few offers.
        fits.sort(
            key=lambda d: (
                -(self.last_seen.get(d["id"], -DAY) > self.now - DAY),
                -d["rating"],
            )
        )
        fee = max(1, int(action["schedule"][0]["feeCents"] * self.p.offer_mult + 0.5))
        for d in fits[: self.p.offer_n]:
            self.offers_sent[(d["id"], day)] = self.offers_sent.get((d["id"], day), 0) + 1
            self.outbox.append({"type": "offer", "gigId": gig_id, "driverId": d["id"], "feeCents": fee})

    def offer_return(self, gig_id: str, order_id: str, leg: int, place: str) -> None:
        """After a driver's last delivery in one of our gigs, offers them our open gig that starts within return_km
        of here and ends nearest their home, if nearer than here: the trip home pays them, so they take less."""
        p, action, driver = self.p, self.posts.get(gig_id), self.drivers.get(self.driver_of.get(gig_id, ""))
        if not p.return_mult or action is None or driver is None:
            return
        last = action["stops"][-1]
        if (last["orderId"], last["leg"]) != (order_id, leg):
            return  # the driver has more stops in this gig
        day = self.now // DAY
        if self.offers_sent.get((driver["id"], day), 0) >= 3:  # RULES: at most three offers per driver per day
            return
        home, best = driver["homePlaceId"], None
        for other_id, other in self.posts.items():
            if other_id in self.booked or not self.is_live(other_id):
                continue
            if len([t for t in self.offers_open.get(other_id, []) if t > self.now - 10]) >= 3:
                continue  # RULES: at most three open offers per gig
            if not self.fits(driver, other["audience"]):
                continue
            first, final = other["stops"][0], other["stops"][-1]
            pickup = self.orders[first["orderId"]]["legs"][first["leg"]]["pickup"]["placeId"]
            delivery = self.orders[final["orderId"]]["legs"][final["leg"]]["delivery"]["placeId"]
            to_pickup, to_home = self.km(place, pickup), self.km(delivery, home)
            if to_pickup <= p.return_km and to_home < self.km(place, home) and (best is None or to_home < best[0]):
                best = (to_home, other_id, other)
        if best is None:
            return
        _, other_id, other = best
        fee = max(1, int(current_fee(other["schedule"], self.now) * p.return_mult + 0.5))
        self.offers_sent[(driver["id"], day)] = self.offers_sent.get((driver["id"], day), 0) + 1
        self.offers_open.setdefault(other_id, []).append(self.now)
        self.outbox.append({"type": "offer", "gigId": other_id, "driverId": driver["id"], "feeCents": fee})

    def offer_next(self, gig_id: str, driver_id: str) -> None:
        """When a driver books one of our gigs, offers them our unbooked one-car gig that starts nearest to where this
        gig ends and that they can still do after it (HANDBOOK: for a driver who already has one of our gigs, a
        second costs only the extra time and tickets, but the app never tells them of it)."""
        p, driver, action = self.p, self.drivers.get(driver_id), self.posts.get(gig_id)
        day = self.now // DAY
        if not p.next_offer_mult or driver is None or action is None or self.offers_sent.get((driver_id, day), 0) >= 3:
            return
        end = self.gig_end(action["stops"])
        if end is None:
            return
        place, free_at = end
        margin, best = p.pair_margin_h * HOUR, None
        for other_id, stops in self.unbooked_lone_gigs().values():
            if len([t for t in self.offers_open.get(other_id, []) if t > self.now - 10]) >= 3:
                continue  # RULES: at most three open offers per gig
            if not self.fits(driver, self.posts[other_id]["audience"]):
                continue
            pickup, delivery, ready, due, extra = self.span(stops)
            link, drive = self.roads.get((place, pickup)), self.roads.get((pickup, delivery))
            if not (link and drive) or link["km"] > p.pair_km:
                continue
            at = max(free_at + link["minutes"], ready)
            if at > self.slot_limits(stops)[0] or at + drive["minutes"] + extra > due - margin:
                continue
            if best is None or link["km"] < best[0]:
                best = (link["km"], other_id)
        if best is None:
            return
        other_id = best[1]
        fee = max(1, int(current_fee(self.posts[other_id]["schedule"], self.now) * p.next_offer_mult + 0.5))
        self.offers_sent[(driver_id, day)] = self.offers_sent.get((driver_id, day), 0) + 1
        self.offers_open.setdefault(other_id, []).append(self.now)
        self.outbox.append({"type": "offer", "gigId": other_id, "driverId": driver_id, "feeCents": fee})

    def gig_end(self, stops: list[StopRef]) -> tuple[str, int] | None:
        """Where and about when a driver who books this gig now finishes it (chain timing), or None if unknown."""
        t, previous = None, None
        for i in range(0, len(stops), 2):
            pair = stops[i : i + 2]
            if len(pair) != 2 or pair[0]["orderId"] != pair[1]["orderId"] or pair[0]["orderId"] not in self.orders:
                return None
            pickup, delivery, ready, _, extra = self.span(pair)
            drive = self.roads.get((pickup, delivery))
            link = self.roads.get((previous, pickup)) if previous else {"minutes": 0}
            if drive is None or link is None:
                return None
            t = max((t if t is not None else self.now + self.p.pair_lead_min) + link["minutes"], ready)
            t += drive["minutes"] + extra
            previous = delivery
        return (previous, t) if previous else None

    def is_pair(self, gig_id: str) -> bool:
        """True for a gig that carries cars of more than one order (a two-car gig from plan or pair)."""
        return len({stop["orderId"] for stop in self.posts[gig_id]["stops"]}) > 1

    def is_live(self, gig_id: str) -> bool:
        """True while the gig still carries one of its legs (not replaced by a repost, not withdrawn)."""
        return any(
            s["orderId"] in self.orders and self.leg_gigs.get(s["orderId"], {}).get(s["leg"]) == gig_id
            for s in self.posts[gig_id]["stops"]
        )

    @staticmethod
    def fits(driver: DriverProfile, audience: Audience) -> bool:
        """The gig's audience rules (RULES: experienced = rating >= 4.8 and >= 50 gigs)."""
        return (not audience.get("experienced") or (driver["rating"] >= 4.8 and driver["completedGigs"] >= 50)) and (
            not audience.get("manualLicence") or driver["licence"] == "manual"
        )

    def km(self, a: str, b: str) -> float:
        road = self.roads.get((a, b))
        return road["km"] if road else float("inf")


def next_plan_at(now: int, every_h: float) -> int:
    """The next batch-plan minute after now: 07:00, then every every_h hours until 19:00, each day."""
    day, minute = now // DAY, now % DAY
    t = 7 * HOUR
    while t <= 19 * HOUR:
        if t > minute:
            return day * DAY + t
        t += int(every_h * HOUR)
    return (day + 1) * DAY + 7 * HOUR


def current_fee(schedule: list[FeeStep], now: int) -> int:
    """The fee a schedule shows at minute now (its first step before it starts)."""
    fee = schedule[0]["feeCents"]
    for step in schedule:
        if step["at"] <= now:
            fee = step["feeCents"]
    return fee


def retry_from(order: Order, request: PriceRequest, leg: int, now: int) -> int:
    """When to try a car again after not_ready/closed: two hours on, or when the moved deadline says it is ready."""
    promised = next(
        (o["deadline"] for o in request["options"] if o["kind"] == order["option"]),
        order["deadline"],
    )
    delay = max(0, order["deadline"] - promised)
    return max(now + 2 * HOUR, order["legs"][leg]["pickup"]["window"]["from"] + delay)


def undelivered(order: Order) -> list[int]:
    return [leg for leg in range(len(order["legs"])) if order["deliveredAt"][leg] is None]


def without_windows(stops: list[StopRef], before: float) -> list[StopRef]:
    """Drops stop windows that end before `before`, so the world's window (to the end of the world) applies."""
    return [
        {k: v for k, v in stop.items() if k != "window"} if "window" in stop and stop["window"]["to"] < before else stop
        for stop in stops
    ]


def stops_for(
    order: Order,
    legs: list[int],
    note: Note | None,
    retry: Retry,
    facts: notes.Facts | None = None,
    now: int = 0,
    charge_km: float = 0,
    roads: dict | None = None,
) -> list[StopRef]:
    """A pickup and a delivery per leg; a charging stop for an electric car under 30% (with charge_km only on a route
    longer than that); own windows only when narrower. The note is read by notes.py when its facts are given, else by
    the starter's keyword matcher."""
    stops: list[StopRef] = []
    for leg in legs:
        car, pickup, delivery = (
            order["legs"][leg]["car"],
            order["legs"][leg]["pickup"],
            order["legs"][leg]["delivery"],
        )
        if facts is None:
            noted = window_from_note(note, pickup["window"], "pickup")
        else:
            noted = {"from": max(pickup["window"]["from"], facts.ready or 0), "to": pickup["window"]["to"]}
        start = max(noted["from"], retry.pickup_from)
        pickup_window: TimeWindow = {"from": start, "to": max(noted["to"], start)}
        if facts is not None and facts.pickup_hours is not None:  # a driver plans by the stated hours: one day only
            pickup_window = notes.open_interval(pickup_window, facts.pickup_hours, now)
        delivery_base: TimeWindow = {
            "from": delivery["window"]["from"],
            "to": max(delivery["window"]["from"], order["deadline"]),
        }
        if facts is None:
            delivery_window = window_from_note(note, delivery_base, "delivery")
        else:
            due = notes.due(facts, delivery_base["to"])
            delivery_window = {**delivery_base, "to": due} if due >= delivery_base["from"] else delivery_base
        low_battery = car["electric"] and car["chargePercent"] is not None and car["chargePercent"] < 30
        if low_battery and charge_km and roads:  # RULES: the charging stop is needed only on a route over 200 km
            road = roads.get((pickup["placeId"], delivery["placeId"]))
            low_battery = road is None or road["km"] > charge_km
        first: StopRef = {
            "orderId": order["id"],
            "leg": leg,
            "kind": "pickup",
            "withPlates": retry.plates or (facts is not None and facts.plates),
            "withCharging": low_battery,
        }
        second: StopRef = {"orderId": order["id"], "leg": leg, "kind": "delivery"}
        stops += [
            narrower(first, pickup_window, pickup["window"]),
            narrower(second, delivery_window, delivery_base),
        ]
    return stops


def narrower(stop: StopRef, window: TimeWindow, base: TimeWindow) -> StopRef:
    return {**stop, "window": window} if window["from"] > base["from"] or window["to"] < base["to"] else stop


# --- note reading (starter's keyword matcher; matters from level 5) ----------------------------
AFTER = re.compile(
    r"jälkeen|alkaen|aikaisintaan|\bafter\b|\bfrom\b|earliest|not before|ei ennen|valmis|\bready\b|efter|tidigast|inte före|klar",
    re.ASCII,
)
BEFORE = re.compile(r"ennen|mennessä|viim|\bbefore\b|\bby\b|latest|före|senast", re.ASCII)
DELIVERY = re.compile(
    r"toimit|perillä|perille|vastaanot|kohde|deliver|arrive|destination|receiv|leverera|leverans|framme|mottag",
    re.ASCII,
)
CLOCK = re.compile(r"(?:klo|kl\.?)\s*(\d{1,2})(?:[.:](\d{2}))?|\b(\d{1,2})[.:](\d{2})\b", re.ASCII)
RANGE = re.compile(r"\b(\d{1,2})(?:[.:](\d{2}))?\s*[-–]\s*(\d{1,2})(?:[.:](\d{2}))?\b", re.ASCII)


def window_from_note(note: Note | None, window: TimeWindow, stop: str) -> TimeWindow:
    """Narrows a stop's window by clock times found near keywords in the note."""
    if not note:
        return window
    text = note["text"].lower()
    if bool(DELIVERY.search(text)) != (stop == "delivery"):
        return window

    def minutes(hour: int, minute: int) -> int | None:
        return None if hour > 24 or minute > 59 else hour * HOUR + minute

    start, end = window["from"], window["to"]
    for match in RANGE.finditer(text):
        opens, closes = (
            minutes(int(match[1]), int(match[2] or 0)),
            minutes(int(match[3]), int(match[4] or 0)),
        )
        if opens is None or closes is None or opens >= closes:
            continue
        start = max(start, start // DAY * DAY + opens)
        end = min(end, end // DAY * DAY + closes)
    text = RANGE.sub(" ", text)
    for match in CLOCK.finditer(text):
        m = minutes(int(match[1] or match[3]), int(match[2] or match[4] or 0))
        if m is None:
            continue
        time = window["from"] // DAY * DAY + m
        around = text[max(0, match.start() - 16) : match.end() + 16]
        if AFTER.search(around):
            start = max(start, time)
        elif BEFORE.search(around):
            end = min(end, time)
    return {"from": start, "to": end} if start <= end else window
