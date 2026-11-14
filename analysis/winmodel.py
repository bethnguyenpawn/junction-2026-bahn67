"""Fits the chance that a dealer takes our quote, from ended worlds (logistic regression, numpy).

    python analysis/winmodel.py --note "explore l8 1.1-1.9" [--note "explore 1.0-2.0" ...]

Each quoted (not declined) request is one row: our price / list price, the dealer's trust count at that time
(rebuilt from our account), Monday, drivers near the pickup, distance, the dealer's size. Prints the
coefficients to paste into config (Params.win_*) and how well the model predicts.
"""

from __future__ import annotations

import sys
from collections import defaultdict

import numpy as np
from common import client, fetch, worlds_from_args

from dispatch import NOTIFY_KM, straight_km

FEATURES = ["const", "mult", "trust", "monday", "dense", "km100", "big"]


def rows_of(c, wid, places, roads):
    d = fetch(c, wid)
    homes = defaultdict(int)
    for drv in d["roster"]:
        homes[drv["homePlaceId"]] += 1
    near = {
        p: sum(
            n
            for h, n in homes.items()
            if straight_km(places[p], places[h]) <= NOTIFY_KM
        )
        for p in places
    }
    reqs = {rr["request"]["id"]: rr for rr in d["reveal"]["requests"]}
    timeline = [
        (e["at"], e["line"]["orderId"], e["line"]["kind"])
        for e in d["events"]
        if e["kind"] == "ledger"
        and e["line"]["kind"] in ("revenue", "late_refund", "undelivered_penalty")
    ]
    trust, state, seen, ti, rows = defaultdict(int), {}, defaultdict(int), 0, []
    for rr in sorted(reqs.values(), key=lambda rr: rr["request"]["arrivedAt"]):
        r = rr["request"]
        while ti < len(timeline) and timeline[ti][0] <= r["arrivedAt"]:
            _, oid, kind = timeline[ti]
            ti += 1
            dealer, st = reqs[oid]["request"]["dealerId"], state.get(oid)
            if kind == "revenue" and st is None:
                trust[dealer], state[oid] = min(25, trust[dealer] + 1), "counted"
            elif kind != "revenue" and st != "late":
                trust[dealer], state[oid] = (
                    max(0, trust[dealer] - (st == "counted")) // 2,
                    "late",
                )
        seen[r["dealerId"]] += 1
        q = rr.get("quote") or {}
        mults = [
            q[o["kind"]] / o["listPriceCents"] for o in r["options"] if o["kind"] in q
        ]
        if not mults or min(mults) >= 5:
            continue
        leg = r["legs"][0]
        rows.append(
            (
                [
                    1.0,
                    min(mults),
                    trust[r["dealerId"]] / 25,
                    float(r["arrivedAt"] // 1440 == 0),
                    float(near[leg["pickup"]["placeId"]] >= 40),
                    roads[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]["km"]
                    / 100,
                    float(seen[r["dealerId"]] >= 20),
                ],
                float(rr["outcome"] == "won"),
            )
        )
    return rows


def fit(x, y, iters=25):
    """Logistic regression by Newton's method (IRLS) with a tiny ridge for stability."""
    w = np.zeros(x.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-x @ w))
        grad = x.T @ (y - p)
        hess = (x * (p * (1 - p))[:, None]).T @ x + 1e-6 * np.eye(x.shape[1])
        w += np.linalg.solve(hess, grad)
    return w


if __name__ == "__main__":
    notes = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--note"]
    c = client()
    m = c.map()
    places = {p["id"]: p for p in m["places"]}
    roads = {(r["from"], r["to"]): r for r in m["roads"]}
    data = [
        row
        for note in notes
        for wid in worlds_from_args(["--note", note])
        for row in rows_of(c, wid, places, roads)
    ]
    x = np.array([r[0] for r in data])
    y = np.array([r[1] for r in data])
    half = (
        len(x) // 2
    )  # rows are grouped by world: fit on the first worlds, check on the rest
    w = fit(x[:half], y[:half])
    p = 1 / (1 + np.exp(-x[half:] @ w))
    print(f"{len(x)} quotes, win rate {y.mean():.1%}")
    print(
        "held-out log loss %.4f (base rate %.4f)"
        % (
            -np.mean(y[half:] * np.log(p) + (1 - y[half:]) * np.log(1 - p)),
            -np.mean(
                y[half:] * np.log(y[:half].mean())
                + (1 - y[half:]) * np.log(1 - y[:half].mean())
            ),
        )
    )
    print(
        "calibration (held out):",
        "  ".join(
            f"{lo:.1f}-{lo + 0.2:.1f}: pred {p[(p >= lo) & (p < lo + 0.2)].mean():.2f} real {y[half:][(p >= lo) & (p < lo + 0.2)].mean():.2f}"
            for lo in (0, 0.2, 0.4, 0.6, 0.8)
            if ((p >= lo) & (p < lo + 0.2)).sum() > 30
        ),
    )
    w = fit(x, y)
    print("coefficients (all data):")
    for name, value in zip(FEATURES, w):
        print(f"  {name:<7} {value:+.3f}")
