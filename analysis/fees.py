"""Fee analysis over ended practice worlds: where the money goes and when gigs get booked.

    python analysis/fees.py                 # worlds of the last evaluate.py run
    python analysis/fees.py w123 w456 ...   # specific worlds
    python analysis/fees.py --note "L8 baseline: starter behaviour"

Caches each world's events + reveal in results/raw/<world>.json (analysis/common.py).
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

from common import client, fetch, worlds_from_args


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def main() -> None:
    c = client()
    wids = worlds_from_args(sys.argv[1:])
    roads = {(r["from"], r["to"]): r for r in c.map()["roads"]}

    ratio_ref_list, ledger = [], defaultdict(int)
    book_delay, booked_mult = [], []
    by_hour = defaultdict(lambda: [0, 0])  # post hour -> [posted, booked within 60 min]
    by_km = defaultdict(lambda: [0, 0, 0])  # km bucket -> [orders, late, margin cents]
    views_per_gig = []
    for wid in wids:
        d = fetch(c, wid)
        req = {r["request"]["id"]: r["request"] for r in d["reveal"]["requests"]}
        gigs = {g["id"]: g for g in d["snapshot"]["gigs"]}
        order_money = defaultdict(int)
        late = set()
        first_post = {}
        for e in d["events"]:
            k = e["kind"]
            if k == "ledger":
                line = e["line"]
                ledger[line["kind"]] += line["cents"]
                if line["orderId"]:
                    order_money[line["orderId"]] += line["cents"]
                if line["kind"] in ("late_refund", "undelivered_penalty"):
                    late.add(line["orderId"])
            elif k == "gig_booked":
                g = gigs.get(e["gigId"])
                if not g:
                    continue
                oid = g["stops"][0]["orderId"]
                r = req[oid]
                cars = sum(s["kind"] == "pickup" for s in g["stops"])
                ref = r["referenceFeeCents"] * cars / len(r["legs"])
                booked_mult.append(e["feeCents"] / ref)
                book_delay.append(e["at"] - g["postedAt"])
        for g in gigs.values():
            oid = g["stops"][0]["orderId"]
            first_post.setdefault(oid, g["postedAt"])
        views = defaultdict(int)
        for v in d["reveal"]["views"]:
            views[v["gigId"]] += 1
        views_per_gig += list(views.values())
        booked_at = {e["gigId"]: e["at"] for e in d["events"] if e["kind"] == "gig_booked"}
        for g in gigs.values():
            h = (g["postedAt"] % 1440) // 60
            by_hour[h][0] += 1
            if g["id"] in booked_at and booked_at[g["id"]] - g["postedAt"] <= 60:
                by_hour[h][1] += 1
        for oid, r in req.items():
            leg = r["legs"][0]
            km = roads[(leg["pickup"]["placeId"], leg["delivery"]["placeId"])]["km"]
            ratio_ref_list.append(r["referenceFeeCents"] / r["options"][0]["listPriceCents"])
            b = min(int(km // 100) * 100, 600)
            by_km[b][0] += 1
            by_km[b][1] += oid in late
            by_km[b][2] += order_money.get(oid, 0)

    n = len(wids)
    print(f"{n} worlds\n\nLEDGER per week")
    for k, v in sorted(ledger.items(), key=lambda x: x[1]):
        print(f"  {k:22} €{v / 100 / n:>11,.2f}")
    print(f"\nTypical fee / list price: median {st.median(ratio_ref_list):.3f}  p10 {pct(ratio_ref_list, .1):.3f}  p90 {pct(ratio_ref_list, .9):.3f}")
    print(f"Booked fee / typical fee: median {st.median(booked_mult):.2f}  share at 1.0x {sum(abs(m - 1) < .01 for m in booked_mult) / len(booked_mult):.1%}")
    print(f"Minutes post -> booking: p25 {pct(book_delay, .25)}  median {pct(book_delay, .5)}  p75 {pct(book_delay, .75)}  p90 {pct(book_delay, .9)}")
    print(f"Views per gig: median {st.median(views_per_gig)}  mean {st.mean(views_per_gig):.1f}")
    print("\nBy distance (km)   orders  late%   margin/order")
    for b in sorted(by_km):
        o, l, m = by_km[b]
        print(f"  {b:>3}-{b + 99:<4}        {o:>6}  {l / o:5.1%}   €{m / 100 / o:>8,.2f}")
    print("\nPost hour  gigs  booked<=60min")
    for h in sorted(by_hour):
        p, b = by_hour[h]
        print(f"  {h:02d}      {p:>5}  {b / p:6.1%}")


if __name__ == "__main__":
    main()
