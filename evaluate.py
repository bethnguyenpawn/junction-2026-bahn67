"""Benchmark harness: plays our system on fixed seeds and logs the result.

    python evaluate.py --level 1 --seeds 10 [--set open_mult=0.9 ...] [--note "idea"]

Seeds are "l{level}-a", "l{level}-b", ... so every version is compared on the same weeks.
Runs in parallel, never more than 4 unfinished worlds of ours at once (team limit is 8).
Appends one JSON line per run to results/log.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import string
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from spread.client import Client, SpreadError

import config
from main import load_env, play_practice

ROOT = os.path.dirname(os.path.abspath(__file__))
MAX_PARALLEL = 4  # half of the team limit (8): the other 4 slots are for teammates


def git_commit() -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain", "--", "*.py"], cwd=ROOT, text=True).strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def run_seed(level: int, seed: str, params: config.Params) -> dict:
    client = Client()  # one connection per thread
    world = client.create(level=level, seed=seed)
    try:
        score = play_practice(world, level, params, verbose=False)
    except BaseException:
        try:
            world.delete()
        except SpreadError:
            pass
        raise
    return {"seed": seed, "worldId": world.id, **score}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--level", type=int, default=1)
    parser.add_argument("--seeds", type=int, default=10, help="number of seeds, l{level}-a ...")
    parser.add_argument("--seed-prefix", default=None, help="default l{level}")
    parser.add_argument(
        "--preset",
        choices=sorted(config.PRESETS),
        default="starter",
        help="named configuration from config.PRESETS",
    )
    parser.add_argument("--set", nargs="*", default=[], metavar="NAME=VALUE")
    parser.add_argument("--note", default="", help="what this experiment tries")
    parser.add_argument("--parallel", type=int, default=MAX_PARALLEL)
    args = parser.parse_args()
    load_env()
    params = config.from_overrides(args.set, config.PRESETS[args.preset])
    prefix = args.seed_prefix or f"l{args.level}"
    letters = string.ascii_lowercase
    seeds = [f"{prefix}-{letters[i] if i < 26 else i}" for i in range(args.seeds)]

    open_worlds = sum(1 for w in Client().worlds() if not w["ended"])
    workers = max(1, min(args.parallel, MAX_PARALLEL, 8 - open_worlds))
    print(
        f"level {args.level}, {len(seeds)} seeds, {workers} in parallel ({open_worlds} worlds already open), "
        f"preset {args.preset}, overrides {args.set or 'none'}",
        flush=True,
    )

    started = time.time()
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(workers) as pool:
        futures = {pool.submit(run_seed, args.level, s, params): s for s in seeds}
        for fut in as_completed(futures):
            seed = futures[fut]
            try:
                results[seed] = fut.result()
                r = results[seed]
                print(
                    f"  {seed:<8} €{r['marginCents'] / 100:>11,.2f}  {r['onTimeShare']:6.1%} on time  "
                    f"{r['wonOrders']:>4} orders  {r['worldId']}",
                    flush=True,
                )
            except Exception as error:
                print(f"  {seed:<8} FAILED: {error}", file=sys.stderr, flush=True)

    rows = [results[s] for s in seeds if s in results]
    total = sum(r["marginCents"] for r in rows)
    orders = sum(r["wonOrders"] for r in rows)
    on_time = sum(r["onTimeShare"] * r["wonOrders"] for r in rows) / orders if orders else 0.0
    worst = min((r["onTimeShare"] for r in rows), default=0.0)
    print(
        f"\nTOTAL  €{total / 100:,.2f}  ({total / 100 / max(1, len(rows)):,.2f}/week)   on time {on_time:.1%}   "
        f"worst week {worst:.1%}   ranked {sum(r['ranked'] for r in rows)}/{len(rows)}   {time.time() - started:.0f}s"
    )

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    line = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "commit": git_commit(),
        "level": args.level,
        "note": args.note,
        "preset": args.preset,
        "overrides": args.set,
        "params": params.as_dict(),
        "seeds": seeds,
        "totalMarginCents": total,
        "onTimeShare": round(on_time, 4),
        "worstOnTime": round(worst, 4),
        "ranked": sum(r["ranked"] for r in rows),
        "completed": len(rows),
        "runs": [
            {
                k: r[k]
                for k in (
                    "seed",
                    "worldId",
                    "marginCents",
                    "revenueCents",
                    "onTimeShare",
                    "undeliveredShare",
                    "wonOrders",
                    "ranked",
                )
            }
            for r in rows
        ],
    }
    with open(os.path.join(ROOT, "results", "log.jsonl"), "a") as f:
        f.write(json.dumps(line) + "\n")


if __name__ == "__main__":
    main()
