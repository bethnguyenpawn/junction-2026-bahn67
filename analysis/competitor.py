"""Fits the constants of market.py from cached level-8 weeks (results/raw), and checks that learning helps.

    python analysis/competitor.py

Offline: reads only weeks already cached by the other analysis scripts. Each quoted request is one row: our cheapest
option x list minus the delivery place's offset, the dealer's trust share, won or lost. Prints:
1. the price slope and trust effect with one competitor level per day (random-price "explore" weeks);
2. the usual move of each weekday, how much days and weeks differ (half of the weeks);
3. on the other half: how well each estimate predicts the next hour's answers (log loss, lower = better).
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pricing import DEST_OFFSET

RAW = os.path.join(ROOT, "results", "raw")
EXPLORE = ("explore l8 1.1-1.9", "explore 1.0-2.0")  # random prices: the only weeks that show the slope
DAY = 1440


def load() -> dict[str, list[tuple]]:
    """World id -> rows (arrived at, price - dest, trust share, won, explore?) of its quoted requests."""
    worlds = {}
    with open(os.path.join(ROOT, "results", "log.jsonl")) as f:
        runs = [json.loads(line) for line in f]
    for run in runs:
        if run.get("level") == 8:
            for r in run.get("runs", []):
                if os.path.exists(os.path.join(RAW, r["worldId"] + ".json")):
                    worlds[r["worldId"]] = run.get("note", "") in EXPLORE
    out = {}
    for wid, explore in worlds.items():
        with open(os.path.join(RAW, wid + ".json")) as f:
            d = json.load(f)
        reqs = {rr["request"]["id"]: rr for rr in d["reveal"]["requests"]}
        ledger = sorted(
            (e["at"], e["line"]["orderId"], e["line"]["kind"])
            for e in d["events"]
            if e["kind"] == "ledger" and e["line"]["kind"] in ("revenue", "late_refund", "undelivered_penalty")
        )
        trust, state, i, rows = defaultdict(int), {}, 0, []
        for rr in sorted(reqs.values(), key=lambda rr: rr["request"]["arrivedAt"]):
            r = rr["request"]
            while i < len(ledger) and ledger[i][0] <= r["arrivedAt"]:  # rebuild dealer trust (RULES, level 8)
                _, oid, kind = ledger[i]
                i += 1
                if oid in reqs:
                    dealer, st = reqs[oid]["request"]["dealerId"], state.get(oid)
                    if kind == "revenue" and st is None:
                        trust[dealer], state[oid] = min(25, trust[dealer] + 1), "counted"
                    elif kind != "revenue" and st != "late":
                        trust[dealer], state[oid] = max(0, trust[dealer] - (st == "counted")) // 2, "late"
            q = rr.get("quote") or {}
            mults = [q[o["kind"]] / o["listPriceCents"] for o in r["options"] if o["kind"] in q]
            if mults and min(mults) < 5 and r["arrivedAt"] < 5 * DAY:  # quoted to win, Mon-Fri
                dest = DEST_OFFSET.get(r["legs"][0]["delivery"]["placeId"], 0.0)
                rows.append(
                    (r["arrivedAt"], min(mults) - dest, trust[r["dealerId"]] / 25, rr["outcome"] == "won", explore)
                )
        out[wid] = rows
    return out


def fit(x, y, iters=30):
    """Logistic regression by Newton's method with a tiny ridge."""
    w = np.zeros(x.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(x @ w, -30, 30)))
        hess = (x * (p * (1 - p))[:, None]).T @ x + 1e-4 * np.eye(x.shape[1])
        w += np.clip(np.linalg.solve(hess, x.T @ (y - p)), -5, 5)
    return w


def per_day(rows, slope=None, trust=None):
    """One intercept per day (+ slope and trust if not given); returns (intercepts by day, slope, trust)."""
    days = sorted({r[0] // DAY for r in rows})
    x = np.zeros((len(rows), len(days) + 2))
    for n, r in enumerate(rows):
        x[n, days.index(r[0] // DAY)], x[n, -2], x[n, -1] = 1, r[1], r[2]
    y = np.array([float(r[3]) for r in rows])
    if slope is None:
        w = fit(x, y)
        return dict(zip(days, w[:-2])), w[-2], w[-1]
    off = slope * x[:, -2] + trust * x[:, -1]  # slope and trust fixed: fit the intercepts only
    a = np.full(len(days), -slope * 1.3)
    z = x[:, :-2]
    for _ in range(40):
        p = 1 / (1 + np.exp(-np.clip(z @ a + off, -30, 30)))
        a += np.clip((z.T @ (y - p)) / (z.T @ (p * (1 - p)) + 1 / 9), -1, 1)  # days are independent: diagonal
    return dict(zip(days, a)), slope, trust


def main() -> None:
    weeks = load()
    explore = [r for rows in weeks.values() for r in rows if r[4]]
    explore_weeks = {w: rows for w, rows in weeks.items() if rows and rows[0][4]}
    # 1. slope and trust, one level per day, on the random-price weeks (rows grouped by week: days are per week)
    x_rows = [(r[0] + 7 * DAY * i, *r[1:]) for i, rows in enumerate(explore_weeks.values()) for r in rows]
    _, slope, trust = per_day(x_rows)
    print(
        f"{len(weeks)} weeks, {len(explore)} random-price quotes: slope {-slope:.2f} per 1.0x list, trust {trust:.2f}"
    )

    # 2. weekday moves and spreads (x list) on half the weeks
    ids = sorted(weeks)
    train, test = ids[0::2], ids[1::2]
    level = {w: {d: -a / slope for d, a in per_day(weeks[w], slope, trust)[0].items()} for w in train if weeks[w]}
    mean_of = {w: np.mean(list(lv.values())) for w, lv in level.items()}
    weekday = [np.mean([lv[d] - mean_of[w] for w, lv in level.items() if d in lv]) for d in range(5)]
    day_sd = [np.std([lv[d] - mean_of[w] - weekday[d] for w, lv in level.items() if d in lv]) for d in range(5)]
    base, week_sd = np.mean(list(mean_of.values())), np.std(list(mean_of.values()))
    print(f"LEVEL = {base:.3f}  WEEK_SD = {week_sd:.3f}")
    print(
        "WEEKDAY =", tuple(round(float(v), 3) for v in weekday), " DAY_SD =", tuple(round(float(v), 3) for v in day_sd)
    )

    # 3. next-hour log loss on the other half, with market.py's estimator using these constants
    import market

    market.SLOPE, market.TRUST, market.LEVEL = -slope, trust, base
    market.WEEKDAY, market.WEEK_SD, market.DAY_SD = tuple(weekday), week_sd, tuple(day_sd)
    scores = defaultdict(lambda: [0.0, 0])
    for w in test:
        m, rows, answered = market.Market(), sorted(weeks[w]), 0
        for at, price, t, won, _ in rows:
            while rows[answered][0] + 15 <= at:  # the dealer answers 15 minutes after the request
                m.add(*rows[answered][:4])
                answered += 1
            usual = base + market.weekday(at // DAY)
            for name, lv in (("one level for all days", base + np.mean(weekday)), ("+ usual weekday", usual)):
                score(scores[name], lv, price, t, won, -slope, trust)
            score(scores["+ learned week and day"], usual + m.move(at), price, t, won, -slope, trust)
    for name, (loss, n) in scores.items():
        print(f"  {name:<24} log loss {loss / n:.4f}  ({n} quotes, {len(test)} weeks)")


def score(acc, level, price, trust_share, won, slope, trust):
    p = min(max(1 / (1 + np.exp(-(slope * (level - price) + trust * trust_share))), 1e-6), 1 - 1e-6)
    acc[0] -= np.log(p if won else 1 - p)
    acc[1] += 1


if __name__ == "__main__":
    main()
