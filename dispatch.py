"""Dispatch: the desk that answers each event with actions, and the driver fee schedules.

Factored out of the kit's starter (spread/starter.py) with identical behaviour at default
parameters. All fee numbers come from config.Params; `fee_schedule` and `steep_schedule`
are the decision points we tune.
"""

from __future__ import annotations

import re
from typing import NamedTuple, Optional

from spread.client import World
from spread.types import (
    Action,
    ActionResult,
    Audience,
    DeskEvent,
    DeskSnapshot,
    FeeStep,
    Gig,
    Note,
    Order,
    PostAction,
    PriceRequest,
    StopRef,
    TimeWindow,
)

import pricing
from config import DAY, HOUR, Params

_ROADS: dict = {}


def roads_of(client) -> dict:
    """The map's roads keyed by (from, to). The map is the same for every world and costs no token: load once."""
    if not _ROADS:
        _ROADS.update({(r["from"], r["to"]): r for r in client.map()["roads"]})
    return _ROADS

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


# --- fee schedules: the main decision at levels 1-2 -------------------------------------------


def fee_schedule(now: int, fee: float, level: int, p: Params) -> list[FeeStep]:
    """Normal schedule: open_mult x fee, then +raise_per_step x fee every raise_every_min. Level 1: one step."""
    steps = 1 if level == 1 else p.raise_steps
    return [
        {
            "at": now + k * p.raise_every_min,
            "feeCents": max(1, int(fee * (p.open_mult + k * p.raise_per_step) + 0.5)),
        }
        for k in range(steps)
    ]


def steep_schedule(now: int, fee: float, level: int, p: Params) -> list[FeeStep]:
    """After deadline_close: steep_open_mult x fee, then +steep_raise_per_step every steep_every_min. Level 1: one step."""
    steps = 1 if level == 1 else p.steep_steps
    return [
        {
            "at": now + k * p.steep_every_min,
            "feeCents": max(
                1, int(fee * (p.steep_open_mult + k * p.steep_raise_per_step) + 0.5)
            ),
        }
        for k in range(steps)
    ]


class Retry(NamedTuple):
    """How to post a leg again after a failed visit."""

    pickup_from: int = 0
    manual_licence: bool = False
    plates: bool = False


class Desk:
    """What we remember, and our answer to each event. Answers wait in the outbox until sent;
    the world applies them at the current minute."""

    def __init__(self, world: World, level: int, now: int, params: Params, roads: Optional[dict] = None):
        self.world, self.level, self.now, self.p = world, level, now, params
        self.roads = roads or {}  # (from place, to place) -> {"km", "minutes"}
        self.outbox: list[Action] = []
        self.requests: dict[str, PriceRequest] = {}
        self.orders: dict[str, Order] = {}  # won and not cancelled
        self.leg_gigs: dict[
            str, dict[int, str]
        ] = {}  # order id -> leg -> gig carrying the leg
        self.booked: set[str] = set()  # gigs a driver holds now
        self.posts: dict[str, PostAction] = {}  # gig id -> the post that made it
        self.urgent: set[str] = set()  # orders whose deadline warning has come
        self.first_posted: dict[
            str, int
        ] = {}  # order id -> minute its first gig was posted

    def rejoin(self, snapshot: DeskSnapshot, history: list[DeskEvent]) -> None:
        """Rebuilds state from the world after a restart, then answers what was missed."""
        posted: dict[str, list[Gig]] = {}
        self.booked = {
            gig["id"]
            for gig in snapshot["gigs"]
            if gig["status"] in ("booked", "working", "done")
        }
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
        self.requests = {
            e["request"]["id"]: e["request"]
            for e in history
            if e["kind"] == "price_request"
        }
        self.urgent = {e["orderId"] for e in history if e["kind"] == "deadline_close"}
        self.orders = {
            o["id"]: o
            for o in snapshot["orders"]
            if o["id"] in self.requests and o["status"] != "cancelled"
        }
        for order in self.orders.values():
            if order["status"] == "waiting" and not self.gigs_of(order["id"]):
                self.post(order, undelivered(order))
        for event in history:
            order = self.orders.get(event.get("orderId", ""))
            if order is None:
                continue
            if (
                event["kind"] == "visit_failed"
                and order["deliveredAt"][event["leg"]] is None
            ):
                later = [
                    g
                    for g in posted.get(order["id"], [])
                    if g["postedAt"] >= event["at"] and g["id"] != event["gigId"]
                ]
                if not any(
                    stop["leg"] == event["leg"]
                    for gig in later
                    for stop in gig["stops"]
                ):
                    self.retry(order["id"], event["leg"], event["reason"])
        for request in snapshot["openRequests"]:
            self.quote(request)

    def handle(self, event: DeskEvent) -> None:
        kind = event["kind"]
        if kind == "price_request":
            self.quote(event["request"])
        elif kind == "order_won":
            self.win(event["order"])
        elif kind == "order_changed":
            self.change(event["order"])
        elif kind == "order_cancelled":
            for books in (self.orders, self.leg_gigs):
                books.pop(event["orderId"], None)
        elif kind == "visit_failed":
            self.retry(event["orderId"], event["leg"], event["reason"])
        elif kind == "gig_expired":
            self.repost(event["gigId"])
        elif kind == "deadline_close":
            self.raise_fees(event["orderId"])
        elif kind == "gig_booked":
            self.booked.add(event["gigId"])
        elif kind in ("gig_dropped", "no_show"):
            self.booked.discard(event["gigId"])
        elif kind == "delivered":
            self.delivered(event["orderId"], event["leg"], event["at"])

    def delivered(self, order_id: str, leg: int, at: int) -> None:
        self.leg_gigs.get(order_id, {}).pop(leg, None)
        if order_id in self.orders:
            self.orders[order_id]["deliveredAt"][leg] = at

    def quote(self, request: PriceRequest) -> None:
        self.requests[request["id"]] = request
        leg = request["legs"][0]
        road = self.roads.get((leg["pickup"]["placeId"], leg["delivery"]["placeId"]))
        prices = pricing.quote(request, self.level, self.p, road["km"] if road else 0.0, self.backlog(),
                               road["minutes"] if road else 0)
        if prices:
            self.outbox.append(
                {"type": "quote", "requestId": request["id"], "prices": prices}
            )

    def backlog(self) -> int:
        """Won orders with an undelivered car that no driver holds."""
        if not self.p.backlog_k:
            return 0
        return sum(1 for oid, order in self.orders.items()
                   if undelivered(order) and not any(g in self.booked for g in self.gigs_of(oid)))

    def win(self, order: Order) -> None:
        if order["id"] in self.requests and order["id"] not in self.orders:
            self.orders[order["id"]] = order
            self.post(order, undelivered(order))

    def change(self, order: Order) -> None:
        if order["id"] in self.orders:
            self.orders[order["id"]] = order
            if self.withdraw(order["id"]):
                self.post(order, undelivered(order))

    def repost(self, gig_id: str) -> None:
        """Posts a gig again when one of its windows ended before a driver booked it."""
        action = self.posts.get(gig_id)
        if action is None or not any(
            self.leg_gigs.get(s["orderId"], {}).get(s["leg"]) == gig_id
            for s in action["stops"]
        ):
            return
        for stop in action["stops"]:
            self.leg_gigs.get(stop["orderId"], {}).pop(stop["leg"], None)
        order = self.orders.get(action["stops"][0]["orderId"])
        if order is None:
            return
        stops = without_windows(action["stops"], float("inf"))
        self.outbox.append(
            {
                **action,
                "stops": stops,
                "schedule": self.fees_for(order, pickups(action)),
            }
        )

    def raise_fees(self, order_id: str) -> None:
        """From the order's deadline warning on, its unbooked gigs go at the steep fees."""
        order = self.orders.get(order_id)
        if order is None:
            return
        self.urgent.add(order_id)
        self.send_post_of(order_id)
        for gig_id in self.gigs_of(order_id):
            if gig_id not in self.booked:
                new = self.fees_for(order, pickups(self.posts[gig_id]))
                self.outbox.append(
                    {"type": "reprice", "gigId": gig_id, "schedule": new}
                )
                self.posts[gig_id] = {**self.posts[gig_id], "schedule": new}

    def fees_for(self, order: Order, cars: int) -> list[FeeStep]:
        fee = (
            self.requests[order["id"]]["referenceFeeCents"] * cars / len(order["legs"])
        )
        if order["id"] in self.urgent:
            return steep_schedule(self.now, fee, self.level, self.p)
        if self.p.ladder_per_hour > 0:
            return [
                {
                    "at": self.now,
                    "feeCents": max(1, int(fee * self.ladder_mult(order["id"]) + 0.5)),
                }
            ]
        return fee_schedule(self.now, fee, self.level, self.p)

    def ladder_mult(self, order_id: str) -> float:
        hours = (self.now - self.first_posted.get(order_id, self.now)) / HOUR
        return min(self.p.ladder_cap, self.p.open_mult + self.p.ladder_per_hour * hours)

    def tick(self) -> None:
        """Raises the fee of every unbooked, non-urgent gig to the ladder's current target."""
        if self.p.ladder_per_hour <= 0:
            return
        for order_id in list(self.orders):
            if order_id in self.urgent:
                continue
            for gig_id in self.gigs_of(order_id):
                if gig_id in self.booked or gig_id not in self.posts:
                    continue
                post = self.posts[gig_id]
                new = self.fees_for(self.orders[order_id], pickups(post))
                if new[-1]["feeCents"] > post["schedule"][-1]["feeCents"]:
                    self.outbox.append(
                        {"type": "reprice", "gigId": gig_id, "schedule": new}
                    )
                    self.posts[gig_id] = {**post, "schedule": new}

    def retry(self, order_id: str, leg: int, reason: str) -> None:
        if order_id in self.orders:
            order = self.orders[order_id]
            self.leg_gigs.get(order_id, {}).pop(leg, None)
            car_not_there = reason in ("not_ready", "closed")
            pickup_from = (
                retry_from(order, self.requests[order_id], leg, self.now)
                if car_not_there
                else 0
            )
            self.post(
                order,
                [leg],
                Retry(
                    pickup_from,
                    manual_licence=reason == "licence",
                    plates=reason == "no_plates",
                ),
            )

    def post(self, order: Order, legs: list[int], retry: Retry = Retry()) -> None:
        # A premium car needs an experienced driver: the fine is €150 a car.
        audience: Audience = {
            "experienced": any(leg["car"]["premium"] for leg in order["legs"]),
            "manualLicence": retry.manual_licence,
        }
        stops = without_windows(
            stops_for(order, legs, self.requests[order["id"]]["note"], retry), self.now
        )
        self.first_posted.setdefault(order["id"], self.now)
        self.outbox.append(
            {
                "type": "post",
                "stops": stops,
                "audience": audience,
                "schedule": self.fees_for(order, len(legs)),
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

    def withdraw(self, order_id: str) -> bool:
        """Withdraws an order's gigs. False, and nothing withdrawn, when a driver holds one."""
        self.send_post_of(order_id)
        gigs = self.gigs_of(order_id)
        if any(gig_id in self.booked for gig_id in gigs):
            return False
        self.leg_gigs.pop(order_id, None)
        self.outbox += [{"type": "withdraw", "gigId": gig_id} for gig_id in gigs]
        return True

    def send_post_of(self, order_id: str) -> None:
        if any(
            action["type"] == "post" and action["stops"][0]["orderId"] == order_id
            for action in self.outbox
        ):
            self.send()

    def send(self) -> None:
        actions, self.outbox = self.outbox, []
        if actions:
            self.read_results(actions, self.world.act(actions))

    def read_results(self, actions: list[Action], results: list[ActionResult]) -> None:
        for action, result in zip(actions, results):
            if action["type"] == "post" and result["ok"] is True:
                self.carry(action, result["id"])


def retry_from(order: Order, request: PriceRequest, leg: int, now: int) -> int:
    """When to try a car again after not_ready/closed: two hours on, or when the moved deadline says it is ready."""
    promised = next(
        (o["deadline"] for o in request["options"] if o["kind"] == order["option"]),
        order["deadline"],
    )
    delay = max(0, order["deadline"] - promised)
    return max(now + 2 * HOUR, order["legs"][leg]["pickup"]["window"]["from"] + delay)


def undelivered(order: Order) -> list[int]:
    return [
        leg for leg in range(len(order["legs"])) if order["deliveredAt"][leg] is None
    ]


def pickups(action: PostAction) -> int:
    return sum(1 for stop in action["stops"] if stop["kind"] == "pickup")


def without_windows(stops: list[StopRef], before: float) -> list[StopRef]:
    """Drops stop windows that end before `before`, so the world's window (to the end of the world) applies."""
    return [
        {k: v for k, v in stop.items() if k != "window"}
        if "window" in stop and stop["window"]["to"] < before
        else stop
        for stop in stops
    ]


def stops_for(
    order: Order, legs: list[int], note: Note | None, retry: Retry
) -> list[StopRef]:
    """A pickup and a delivery per leg; a charging stop for an electric car under 30%; own windows only when narrower."""
    stops: list[StopRef] = []
    for leg in legs:
        car, pickup, delivery = (
            order["legs"][leg]["car"],
            order["legs"][leg]["pickup"],
            order["legs"][leg]["delivery"],
        )
        noted = window_from_note(note, pickup["window"], "pickup")
        start = max(noted["from"], retry.pickup_from)
        pickup_window: TimeWindow = {"from": start, "to": max(noted["to"], start)}
        delivery_base: TimeWindow = {
            "from": delivery["window"]["from"],
            "to": max(delivery["window"]["from"], order["deadline"]),
        }
        delivery_window = window_from_note(note, delivery_base, "delivery")
        low_battery = (
            car["electric"]
            and car["chargePercent"] is not None
            and car["chargePercent"] < 30
        )
        first: StopRef = {
            "orderId": order["id"],
            "leg": leg,
            "kind": "pickup",
            "withPlates": retry.plates,
            "withCharging": low_battery,
        }
        second: StopRef = {"orderId": order["id"], "leg": leg, "kind": "delivery"}
        stops += [
            narrower(first, pickup_window, pickup["window"]),
            narrower(second, delivery_window, delivery_base),
        ]
    return stops


def narrower(stop: StopRef, window: TimeWindow, base: TimeWindow) -> StopRef:
    return (
        {**stop, "window": window}
        if window["from"] > base["from"] or window["to"] < base["to"]
        else stop
    )


# --- note reading (starter's keyword matcher; matters from level 5) ----------------------------
AFTER = re.compile(
    r"jälkeen|alkaen|aikaisintaan|\bafter\b|\bfrom\b|earliest|not before|ei ennen|valmis|\bready\b|efter|tidigast|inte före|klar",
    re.ASCII,
)
BEFORE = re.compile(
    r"ennen|mennessä|viim|\bbefore\b|\bby\b|latest|före|senast", re.ASCII
)
DELIVERY = re.compile(
    r"toimit|perillä|perille|vastaanot|kohde|deliver|arrive|destination|receiv|leverera|leverans|framme|mottag",
    re.ASCII,
)
CLOCK = re.compile(
    r"(?:klo|kl\.?)\s*(\d{1,2})(?:[.:](\d{2}))?|\b(\d{1,2})[.:](\d{2})\b", re.ASCII
)
RANGE = re.compile(
    r"\b(\d{1,2})(?:[.:](\d{2}))?\s*[-–]\s*(\d{1,2})(?:[.:](\d{2}))?\b", re.ASCII
)


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
