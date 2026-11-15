"""Fits the chance that a won order arrives late, from ended worlds (logistic regression, numpy).

    python analysis/latemodel.py --note "dense0.2 priv0.2 " [--note ...]

One row per won order, with what we knew when we quoted it: slack (deadline of the won option - road minutes
- the quote's respondBy), distance, private address, drivers near the pickup and the delivery, our backlog
(won orders without a driver), the hour. Prints the coefficients for Params.late_*.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict

import numpy as np

from common import client, fetch, worlds_from_args
from dispatch import NOTIFY_KM, straight_km
from winmodel import fit

FEATURES = ["const", "slack24", "km100", "private", "near_pu", "near_de", "backlog10", "late_hour"]


def rows_of(c, wid, places, roads):
    d = fetch(c, wid)
    homes = defaultdict(int)
    for drv in d["roster"]:
        homes[drv["homePlaceId"]] += 1
    near = {p: sum(n for h, n in homes.items() if straight_km(places[p], places[h]) <= NOTIFY_KM) for p in places}
    reqs = {rr["request"]["id"]: rr for rr in d["reveal"]["requests"]}
    gig_order = {g["id"]: g["stops"][0]["orderId"] for g in d["snapshot"]["gigs"]}
    late = {
        e["line"]["orderId"]
        for e in d["events"]
        if e["kind"] == "ledger" and e["line"]["kind"] in ("late_refund", "undelivered_penalty")
    }
    cancelled = {o["id"] for o in d["snapshot"]["orders"] if o["status"] == "cancelled"}
    open_orders, booked, rows = set(), set(), []
    for e in d["events"]:  # replay the week to know our backlog when each request came in
        kind = e["kind"]
        if kind == "price_request":
            r = e["request"]
            rr = reqs.get(r["id"])
            if rr is None or rr["outcome"] != "won" or r["id"] in cancelled:
                continue
            option = next(o for o in r["options"] if o["kind"] == rr["option"])
            leg = r["legs"][0]
            pu, de = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
            slack = option["deadline"] - roads[(pu, de)]["minutes"] - r["respondBy"]
            backlog = len(open_orders - booked)
            rows.append(
                (
                    [
                        1.0,
                        slack / 1440,
                        roads[(pu, de)]["km"] / 100,
                        float(leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"]),
                        math.log1p(near[pu]) / 4,
                        math.log1p(near[de]) / 4,
                        backlog / 10,
                        float((r["arrivedAt"] % 1440) >= 15 * 60),
                    ],
                    float(r["id"] in late),
                )
            )
        elif kind == "order_won":
            open_orders.add(e["order"]["id"])
        elif kind == "gig_booked" and e["gigId"] in gig_order:
            booked.add(gig_order[e["gigId"]])
        elif kind in ("gig_dropped", "no_show") and e["gigId"] in gig_order:
            booked.discard(gig_order[e["gigId"]])
        elif kind in ("delivered", "order_cancelled"):
            open_orders.discard(e["orderId"])
            booked.discard(e["orderId"])
    return rows


if __name__ == "__main__":
    notes = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--note"]
    c = client()
    m = c.map()
    places = {p["id"]: p for p in m["places"]}
    roads = {(r["from"], r["to"]): r for r in m["roads"]}
    data = [
        row for note in notes for wid in worlds_from_args(["--note", note]) for row in rows_of(c, wid, places, roads)
    ]
    x = np.array([r[0] for r in data])
    y = np.array([r[1] for r in data])
    half = len(x) // 2
    w = fit(x[:half], y[:half])
    p = 1 / (1 + np.exp(-x[half:] @ w))
    base = y[:half].mean()
    print(f"{len(x)} won orders, late {y.mean():.1%}")
    print(
        "held-out log loss %.4f (base rate %.4f)"
        % (
            -np.mean(y[half:] * np.log(p) + (1 - y[half:]) * np.log(1 - p)),
            -np.mean(y[half:] * np.log(base) + (1 - y[half:]) * np.log(1 - base)),
        )
    )
    order = np.argsort(p)
    for q in (0.5, 0.8, 0.9, 0.95):
        top = order[int(q * len(order)) :]
        print(f"  riskiest {1 - q:.0%} by the model: real late {y[half:][top].mean():.1%}")
    w = fit(x, y)
    print("coefficients (all data):")
    for name, value in zip(FEATURES, w):
        print(f"  {name:<10} {value:+.3f}")
