"""Per-order view of ended worlds: which orders are late or lose money, by distance, town, option, hour.

    python analysis/orders.py --note "L8 baseline: starter behaviour"
"""
from __future__ import annotations

import sys
from collections import defaultdict

from common import client, fetch, worlds_from_args


def table(title, groups, key_fmt=str, min_n=30):
    print(f"\n{title:<26} orders  late%  margin/order  list€  booked-fee/typical")
    for k in sorted(groups, key=lambda k: (isinstance(k, str), k)):
        g = groups[k]
        n = len(g)
        if n < min_n:
            continue
        late = sum(o["late"] for o in g) / n
        m = sum(o["margin"] for o in g) / n / 100
        lp = sum(o["list"] for o in g) / n / 100
        fm = [o["feemult"] for o in g if o["feemult"]]
        fmm = sorted(fm)[len(fm) // 2] if fm else float("nan")
        print(f"  {key_fmt(k):<24} {n:>6}  {late:5.1%}  €{m:>10,.2f}  {lp:>5.0f}  {fmm:5.2f}")


def main():
    c = client()
    wids = worlds_from_args(sys.argv[1:])
    places = {p["id"]: p["name"] for p in c.map()["places"]}
    roads = {(r["from"], r["to"]): r for r in c.map()["roads"]}
    orders = []
    for wid in wids:
        d = fetch(c, wid)
        gigs = {g["id"]: g for g in d["snapshot"]["gigs"]}
        money, late = defaultdict(int), set()
        booked = defaultdict(list)
        for e in d["events"]:
            if e["kind"] == "ledger":
                l = e["line"]
                if l["orderId"]:
                    money[l["orderId"]] += l["cents"]
                if l["kind"] in ("late_refund", "undelivered_penalty"):
                    late.add(l["orderId"])
            elif e["kind"] == "gig_booked" and e["gigId"] in gigs:
                booked[gigs[e["gigId"]]["stops"][0]["orderId"]].append(e["feeCents"])
        cancelled = {o["id"] for o in d["snapshot"]["orders"] if o["status"] == "cancelled"}
        for rr in d["reveal"]["requests"]:
            if rr["outcome"] != "won" or rr["request"]["id"] in cancelled:
                continue
            r = rr["request"]
            leg = r["legs"][0]
            km = roads[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]["km"]
            ref = r["referenceFeeCents"]
            orders.append({
                "km": km, "late": r["id"] in late, "margin": money.get(r["id"], 0),
                "list": next(o["listPriceCents"] for o in r["options"] if o["kind"] == rr["option"]),
                "feemult": (max(booked[r["id"]]) / (ref / len(r["legs"]))) if booked.get(r["id"]) else None,
                "from": places[leg["pickup"]["placeId"]], "to": places[leg["delivery"]["placeId"]],
                "option": rr["option"], "hour": (r["arrivedAt"] % 1440) // 60, "day": r["arrivedAt"] // 1440,
                "legs": len(r["legs"]), "private": leg["pickup"]["privateAddress"] or leg["delivery"]["privateAddress"],
                "reflist": ref / r["options"][0]["listPriceCents"],
            })
    n = len(orders)
    print(f"{len(wids)} worlds, {n} won orders, late {sum(o['late'] for o in orders) / n:.1%}, "
          f"margin/order €{sum(o['margin'] for o in orders) / n / 100:,.2f}")
    by = lambda f: (lambda g: [g[f(o)].append(o) for o in orders] and g)(defaultdict(list))
    table("By distance (km)", by(lambda o: min(int(o["km"] // 100) * 100, 600)), lambda k: f"{k}-{k + 99}")
    table("By option", by(lambda o: o["option"]))
    table("By weekday of request", by(lambda o: o["day"]), lambda k: ["Mon", "Tue", "Wed", "Thu", "Fri"][k] if k < 5 else k)
    table("By hour of request", by(lambda o: o["hour"]), lambda k: f"{k:02d}:00")
    table("By legs / private", by(lambda o: f"{o['legs']} legs, private={o['private']}"))
    table("By pickup town", by(lambda o: o["from"]), min_n=150)
    table("By delivery town", by(lambda o: o["to"]), min_n=150)


if __name__ == "__main__":
    main()
