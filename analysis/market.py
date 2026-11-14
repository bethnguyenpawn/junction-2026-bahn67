"""Market view of ended worlds: what we quoted, won and lost, and how the drivers near a town shape margin.

    python analysis/market.py --note "L8 l8: l8v3 decline550"
"""
from __future__ import annotations

import sys
from collections import defaultdict

from common import client, fetch, worlds_from_args

from dispatch import NOTIFY_KM, straight_km


def table(title, groups, cols, min_n=20):
    print(f"\n{title}")
    print("  " + f"{'':<16}" + "".join(f"{c[0]:>12}" for c in cols))
    for k in sorted(groups, key=lambda k: (isinstance(k, str), k)):
        g = groups[k]
        if len(g) < min_n:
            continue
        print("  " + f"{str(k):<16}" + "".join(f"{c[1](g):>12}" for c in cols))


def main():
    c = client()
    wids = worlds_from_args(sys.argv[1:])
    m = c.map()
    places = {p["id"]: p for p in m["places"]}
    roads = {(r["from"], r["to"]): r for r in m["roads"]}
    reqs, orders = [], []
    for wid in wids:
        d = fetch(c, wid)
        homes = defaultdict(int)
        for drv in d["roster"]:
            homes[drv["homePlaceId"]] += 1
        near = {p: sum(n for h, n in homes.items() if straight_km(places[p], places[h]) <= NOTIFY_KM) for p in places}
        money, late = defaultdict(int), set()
        fees = defaultdict(int)
        for e in d["events"]:
            if e["kind"] == "ledger":
                line = e["line"]
                if line["orderId"]:
                    money[line["orderId"]] += line["cents"]
                    if line["kind"] == "driver_fee":
                        fees[line["orderId"]] -= line["cents"]
                if line["kind"] in ("late_refund", "undelivered_penalty"):
                    late.add(line["orderId"])
        cancelled = {o["id"] for o in d["snapshot"]["orders"] if o["status"] == "cancelled"}
        for rr in d["reveal"]["requests"]:
            r = rr["request"]
            leg = r["legs"][0]
            pu, de = leg["pickup"]["placeId"], leg["delivery"]["placeId"]
            first = r["options"][0]
            q = rr.get("quote") or {}
            mult = min((q[o["kind"]] / o["listPriceCents"] for o in r["options"] if o["kind"] in q), default=None)
            row = {"km": roads[(pu, de)]["km"], "near_pu": near[pu], "near_de": near[de], "mult": mult,
                   "outcome": rr["outcome"], "list": first["listPriceCents"], "ref": r["referenceFeeCents"],
                   "hour": (r["arrivedAt"] % 1440) // 60, "day": r["arrivedAt"] // 1440, "legs": len(r["legs"])}
            reqs.append(row)
            if rr["outcome"] == "won" and r["id"] not in cancelled:
                row = dict(row, margin=money.get(r["id"], 0), late=r["id"] in late, fee=fees.get(r["id"], 0),
                           option=rr["option"])
                orders.append(row)
    n = len(wids)
    quoted = [r for r in reqs if r["mult"] is not None and r["mult"] < 5]
    declined = [r for r in reqs if r["mult"] is not None and r["mult"] >= 5]
    print(f"{n} worlds: {len(reqs) / n:.0f} requests/week, quoted {len(quoted) / n:.0f}, declined {len(declined) / n:.0f}, "
          f"won {sum(r['outcome'] == 'won' for r in quoted) / n:.0f} ({sum(r['outcome'] == 'won' for r in quoted) / max(1, len(quoted)):.0%} of quoted)")
    print(f"won orders/week {len(orders) / n:.0f}, margin/order €{sum(o['margin'] for o in orders) / len(orders) / 100:.2f}, "
          f"late {sum(o['late'] for o in orders) / len(orders):.1%}")
    win = ("win%", lambda g: f"{sum(r['outcome'] == 'won' for r in g) / len(g):.0%}")
    cnt = ("n/week", lambda g: f"{len(g) / n:.1f}")
    late = ("late%", lambda g: f"{sum(o['late'] for o in g) / len(g):.1%}")
    marg = ("margin/ord", lambda g: f"{sum(o['margin'] for o in g) / len(g) / 100:.0f}")
    tot = ("margin/wk", lambda g: f"{sum(o['margin'] for o in g) / n / 100:.0f}")
    feer = ("fee/ref", lambda g: f"{sorted(o['fee'] / o['ref'] for o in g)[len(g) // 2]:.2f}")
    refl = ("ref/list", lambda g: f"{sum(o['ref'] / o['list'] for o in g) / len(g):.2f}")

    def by(rows, f):
        g = defaultdict(list)
        for r in rows:
            g[f(r)].append(r)
        return g

    bucket = lambda v: "0" if v == 0 else "1-4" if v < 5 else "5-14" if v < 15 else "15-39" if v < 40 else "40+"
    table("Quoted requests by quote/list", by(quoted, lambda r: round(r["mult"], 2)), [cnt, win])
    table("Quoted by drivers within 30 km of pickup", by(quoted, lambda r: bucket(r["near_pu"])), [cnt, win, refl])
    table("ALL requests by drivers near pickup", by(reqs, lambda r: bucket(r["near_pu"])), [cnt, refl])
    table("Won orders by drivers near pickup", by(orders, lambda r: bucket(r["near_pu"])), [cnt, late, marg, tot, feer])
    table("Won orders by drivers near delivery", by(orders, lambda r: bucket(r["near_de"])), [cnt, late, marg, tot, feer])
    table("Won orders by km", by(orders, lambda r: min(int(r["km"] // 100) * 100, 500)), [cnt, late, marg, tot, feer, refl])
    table("Declined by km", by(declined, lambda r: min(int(r["km"] // 100) * 100, 600)), [cnt])
    table("Won by option", by(orders, lambda r: r["option"]), [cnt, late, marg, tot, feer])


if __name__ == "__main__":
    main()
