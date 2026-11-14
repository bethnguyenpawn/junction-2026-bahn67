"""The typical fee without its noise: the mean log typical fee of each lane, from every cached request.

    python analysis/typical.py        # writes fees.json next to dispatch.py

HANDBOOK: the world starts the typical fee from the work's cost to a typical driver who lives in the pickup town,
scales it by one factor on every lane, and adds a noise for each request. Over the cached weeks the noise is ~11%
(log std within a lane); the lane, the hour, the battery and the deadline explain under 9% of it, and the level does not
move between worlds (0.2%). Drivers book by their own cost, not by the noisy number, so a fee built on the lane's
mean pays less where the noise came out high (Params.fee_lane, Exp. 61).

Key: "pickup>delivery>private>premium" (private and premium as 0/1) -> [mean log fee in cents, requests].
"""

from __future__ import annotations

import glob
import json
import math
import os
from collections import defaultdict

from common import RAW, ROOT

from pricing import lane_key


def main() -> None:
    seen: set[tuple] = set()  # the same seed replays the same requests: count each once
    logs: dict[str, list[float]] = defaultdict(list)
    for path in sorted(glob.glob(os.path.join(RAW, "*.json"))):
        with open(path) as f:
            events = json.load(f)["events"]
        for event in events:
            if event["kind"] != "price_request" or len(event["request"]["legs"]) != 1:
                continue
            request = event["request"]
            leg = request["legs"][0]
            key = lane_key(leg)
            sample = (request["id"], request["arrivedAt"], key, request["referenceFeeCents"])
            if sample not in seen:
                seen.add(sample)
                logs[key].append(math.log(request["referenceFeeCents"]))
    table = {key: [round(sum(v) / len(v), 5), len(v)] for key, v in sorted(logs.items())}
    with open(os.path.join(ROOT, "fees.json"), "w") as f:
        json.dump(table, f, separators=(",", ":"))
    print(f"{len(seen)} distinct one-car requests, {len(table)} lanes -> fees.json")


if __name__ == "__main__":
    main()
