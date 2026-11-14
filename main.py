"""Runs our system on a world: the practice advance loop and the final's live stream loop.

    python main.py --level 1 --seed l1-a [--set open_mult=0.9 ...]
    python main.py --final

    python main.py --board --level 8 --preset l8      # one RANKING run: counts on the practice leaderboard

A ranking run plays the next secret week of the current round (5 per level per round, each once).
It can't be revealed or forked, and deleting it doesn't remove it, so we never auto-delete one.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback
from typing import Optional

from spread.client import Client, SpreadError, Unreachable, World
from spread.types import Score

import config
from config import DAY, Params
from dispatch import WAKE_ON, Desk, drivers_near, places_of, roads_of

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def load_env(path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")) -> None:
    """Reads SPREAD_URL / SPREAD_KEY from .env when they are not already set. Never prints them."""
    if not os.path.exists(path):
        return
    for line in open(path):
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_near(world: World, params: Params) -> Optional[dict]:
    """Drivers living near each place, from the world's driver list; only when a rule uses it (one extra read)."""
    if not (params.dense_n or params.sparse_n or params.offer_mult):
        return None
    return drivers_near(world.roster(), places_of(world.client))


def play_practice(world: World, level: int, params: Params, verbose: bool = True) -> Score:
    """Steps the world from one event that needs an answer to the next; one request per step."""
    snapshot = world.snapshot()
    desk = Desk(world, level, snapshot["now"], params, roads_of(world.client), load_near(world, params))
    ends_at = snapshot["endsAt"]
    seen = -1
    while desk.now < ends_at:
        day, midnight = desk.now // DAY, (desk.now // DAY + 1) * DAY
        actions, desk.outbox = desk.outbox, []
        stop_at = min(ends_at, midnight)
        if params.ladder_per_hour > 0:
            stop_at = min(stop_at, desk.now + params.tick_min)
        step = world.advance(until=WAKE_ON, max=stop_at, actions=actions)
        desk.read_results(actions, step["results"])
        desk.now = step["now"]
        for event in step["events"]:
            if event["seq"] <= seen:  # drop repeats after a server restart
                continue
            seen = event["seq"]
            desk.handle(event)
        desk.tick()
        if verbose and desk.now // DAY > day:
            report(WEEKDAYS[day % 7], world.score())
    return world.score()


def play_final(world: World, params: Params) -> None:
    """Rebuilds state from the world, then answers events from the live stream."""
    history = world.events()
    snapshot = world.snapshot()
    if snapshot["now"] >= snapshot["endsAt"]:
        return
    level = next((w["level"] for w in world.client.worlds() if w["worldId"] == world.id), 8)
    desk = Desk(world, level, snapshot["now"], params, roads_of(world.client), load_near(world, params))
    desk.rejoin(snapshot, history)
    desk.send()
    for event in world.stream(after=history[-1]["seq"] if history else -1, idle=1.0):
        day = desk.now // DAY
        desk.now = world.client.final()["now"] if event is None else max(desk.now, event["at"])
        if event is not None:
            try:
                desk.handle(event)
            except Exception:  # one odd event must not stop the week: log it, skip it, go on
                print(f"Skipped event {event.get('seq')} ({event.get('kind')}):", file=sys.stderr)
                traceback.print_exc()
        desk.tick()
        desk.send()
        if desk.now // DAY > day:
            report(WEEKDAYS[day % 7], world.score())
        if desk.now >= snapshot["endsAt"]:
            return


def report(label: str, score: Score) -> None:
    orders = f"{score['wonOrders']:>4} orders  {score['onTimeShare']:6.1%} on time  {score['undeliveredShare']:5.1%} not delivered"
    print(f"{label:<9}  margin €{score['marginCents'] / 100:>11,.2f}  revenue €{score['revenueCents'] / 100:>11,.2f}  {orders}", flush=True)


def next_final(client: Client) -> World:
    """Waits until a final is set and not yet ended."""
    said = False
    while True:
        try:
            world: Optional[World] = client.world(client.final()["worldId"])
        except SpreadError as error:
            if error.status != 404:
                raise
            world = None
        if world is not None:
            snapshot = world.snapshot()
            if snapshot["now"] < snapshot["endsAt"]:
                return world
        if not said:
            print("No final is set. Waiting for it.", flush=True)
            said = True
        time.sleep(10)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plays a Spread world with our system.")
    parser.add_argument("--level", type=int, choices=range(1, 9), default=1)
    parser.add_argument("--seed")
    parser.add_argument("--final", action="store_true", help="play our copy of the final from the live stream")
    parser.add_argument("--board", action="store_true", help="play our next RANKING run at the level (counts on the practice leaderboard)")
    parser.add_argument("--preset", choices=sorted(config.PRESETS), default="starter", help="named configuration from config.PRESETS")
    parser.add_argument("--set", nargs="*", default=[], metavar="NAME=VALUE", help="override parameters from config.Params")
    args = parser.parse_args()
    load_env()
    params = config.from_overrides(args.set, config.PRESETS[args.preset])
    try:
        client = Client()
        if args.final:
            world = None
            while True:  # a server restart drops connections; rebuild from the world and go on
                try:
                    if world is None:
                        world = next_final(client)
                        print(f"Final world {world.id}.", flush=True)
                    play_final(world, params)
                    break
                except Unreachable as error:
                    print(f"spread: {error}. Trying again in 5 seconds.", file=sys.stderr, flush=True)
                    time.sleep(5)
                except Exception:  # any other failure: rebuild from the world and go on; the clock does not wait
                    traceback.print_exc()
                    print("Rebuilding from the world in 2 seconds.", file=sys.stderr, flush=True)
                    time.sleep(2)
            score = world.score()
        else:
            if args.board and args.seed:
                sys.exit("--board plays the round's secret week: it takes no --seed.")
            world = client.create(level=args.level, seed=args.seed, board=args.board)
            kind = "Ranking run" if args.board else "Practice world"
            print(f"{kind} {world.id}, level {args.level}, preset {args.preset}.", flush=True)
            try:
                score = play_practice(world, args.level, params)
            except BaseException:
                if args.board:  # deleting a ranking run doesn't remove it: leave it, it plays on without us
                    print(f"{kind} {world.id} stopped; it counts with whatever it scores.", file=sys.stderr)
                    raise
                try:
                    world.delete()  # free the practice slot
                except SpreadError:
                    pass
                raise
        report("End", score)
        print("Ranked." if score["ranked"] else "Not ranked.")
    except SpreadError as error:
        sys.exit(f"spread: {error}")
    except KeyboardInterrupt:
        sys.exit("Stopped.")


if __name__ == "__main__":
    main()
