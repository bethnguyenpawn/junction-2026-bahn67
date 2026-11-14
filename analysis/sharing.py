"""How many cars share a driver, and what a car costs in driver fees, alone vs. in a multi-car gig.

python analysis/sharing.py --note "plan2 + chains 3"
"""

import sys
from collections import Counter, defaultdict

from common import client, fetch, worlds_from_args


def main() -> None:
    c = client()
    worlds = worlds_from_args(sys.argv[1:])
    cars, fees, typical, sizes = Counter(), Counter(), Counter(), Counter()
    for wid in worlds:
        data = fetch(c, wid)
        events = data["events"]
        requests = {e["request"]["id"]: e["request"] for e in events if e["kind"] == "price_request"}
        gigs = {g["id"]: g for g in data["snapshot"]["gigs"]}
        paid = defaultdict(int)
        for e in events:
            if e["kind"] == "ledger" and e["line"]["kind"] == "driver_fee":
                paid[e["line"]["gigId"]] -= e["line"]["cents"]
        for gig_id, fee in paid.items():
            orders = {stop["orderId"] for stop in gigs[gig_id]["stops"]}
            kind = "alone" if len(orders) == 1 else "shared"
            sizes[len(orders)] += 1
            cars[kind] += len(orders)
            fees[kind] += fee
            typical[kind] += sum(requests[o]["referenceFeeCents"] for o in orders)
    weeks, total = len(worlds), cars["alone"] + cars["shared"]
    for kind in ("shared", "alone"):
        print(
            f"{kind:6}: {cars[kind] / weeks:5.0f} cars/week ({cars[kind] / total:.0%})  "
            f"fee/car €{fees[kind] / cars[kind] / 100:5.2f}  fee ÷ typical {fees[kind] / typical[kind]:.2f}"
        )
    print("gigs by cars:", {n: round(k / weeks, 1) for n, k in sorted(sizes.items())}, "per week")


if __name__ == "__main__":
    main()
