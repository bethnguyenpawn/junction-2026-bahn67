"""Shared loading for analysis scripts: pick worlds from results/log.jsonl, cache events + reveal."""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from spread.client import Client  # noqa: E402

from main import load_env  # noqa: E402

RAW = os.path.join(ROOT, "results", "raw")


def worlds_from_args(argv: list[str]) -> list[str]:
    """`--note TEXT` = worlds of the last logged run with that note; world ids; or nothing = last run."""
    log = [json.loads(l) for l in open(os.path.join(ROOT, "results", "log.jsonl"))]
    if argv[:1] == ["--note"]:
        runs = [x for x in log if x["note"] == argv[1]]
        if not runs:
            raise SystemExit(f"No logged run with note {argv[1]!r}")
        return [r["worldId"] for r in runs[-1]["runs"]]
    return argv or [r["worldId"] for r in log[-1]["runs"]]


def client() -> Client:
    load_env()
    return Client()


def fetch(c: Client, wid: str) -> dict:
    path = os.path.join(RAW, f"{wid}.json")
    if os.path.exists(path):
        return json.load(open(path))
    w = c.world(wid)
    data = {"events": w.events(), "reveal": w.reveal(), "snapshot": w.snapshot()}
    os.makedirs(RAW, exist_ok=True)
    json.dump(data, open(path, "w"))
    return data
