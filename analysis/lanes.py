"""Fits how much dearer or cheaper the competitor is for cars going to each place, and writes lanes.json.

    python analysis/lanes.py --note "explore 1.0-2.0" --note "explore l8 1.1-1.9"

HANDBOOK ("Dealers compare prices"): the competitor's lane factor is higher where little work comes back and few
drivers live near the delivery place, and this part is almost the same in every world. So we add one indicator per
delivery place to the win model (analysis/winmodel.py) and fit it on random-price quotes. The check fits on seeds
a-e and tests on f-j, other worlds: if the places help there, the effect is the same across worlds.
The offsets are centred on the average quote and divided by the price coefficient, so they are in x list price:
pricing.flat_mult adds dest_k x offset.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
from common import client, fetch, worlds_from_args
from winmodel import rows_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RIDGE = 1.0  # keeps the offsets of rarely seen places near zero


def deliveries_of(c, wid):
    """The delivery place of each quoted request, in the same order as winmodel.rows_of."""
    out = []
    for rr in sorted(fetch(c, wid)["reveal"]["requests"], key=lambda rr: rr["request"]["arrivedAt"]):
        r, q = rr["request"], rr.get("quote") or {}
        mults = [q[o["kind"]] / o["listPriceCents"] for o in r["options"] if o["kind"] in q]
        if mults and min(mults) < 5:
            out.append(r["legs"][0]["delivery"]["placeId"])
    return out


def fit(x, y):
    """Logistic regression (Newton) with a ridge penalty."""
    w = np.zeros(x.shape[1])
    for _ in range(25):
        p = 1 / (1 + np.exp(-x @ w))
        hess = (x * (p * (1 - p))[:, None]).T @ x + RIDGE * np.eye(x.shape[1])
        w += np.linalg.solve(hess, x.T @ (y - p) - RIDGE * w)
    return w


def log_loss(w, x, y):
    p = np.clip(1 / (1 + np.exp(-x @ w)), 1e-6, 1 - 1e-6)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


if __name__ == "__main__":
    notes = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--note"]
    c = client()
    m = c.map()
    places = {p["id"]: p for p in m["places"]}
    roads = {(r["from"], r["to"]): r for r in m["roads"]}
    pids = sorted(places)
    base, dest, train, y = [], [], [], []
    for note in notes:
        wids = worlds_from_args(["--note", note])  # in seed order a, b, ...
        for i, wid in enumerate(wids):
            rows, deliveries = rows_of(c, wid, places, roads), deliveries_of(c, wid)
            assert len(rows) == len(deliveries)
            base += [r[0] for r in rows]
            y += [r[1] for r in rows]
            dest += deliveries
            train += [i < len(wids) // 2] * len(rows)  # first half of the seeds; the rest are other worlds
    onehot = np.array([[float(d == p) for p in pids[1:]] for d in dest])  # first place = reference
    x0, x1, y = np.array(base), np.hstack([np.array(base), onehot]), np.array(y)
    train = np.array(train)
    print(f"{len(y)} quotes")
    for name, x in (("without places", x0), ("with delivery place", x1)):
        print(f"  {name:<20} held-out log loss {log_loss(fit(x[train], y[train]), x[~train], y[~train]):.4f}")
    w = fit(x1, y)
    effect = np.concatenate([[0.0], w[x0.shape[1] :]])
    effect -= np.mean(effect[[pids.index(d) for d in dest]])  # centre on the average quote
    offsets = {p: round(float(e / -w[1]), 3) for p, e in zip(pids, effect)}
    with open(os.path.join(ROOT, "lanes.json"), "w") as f:
        json.dump(offsets, f, indent=0, sort_keys=True)
    for p in sorted(pids, key=offsets.get):
        print(f"  {places[p]['name']:<14} {offsets[p]:+.3f}x list  ({dest.count(p)} quotes)")
