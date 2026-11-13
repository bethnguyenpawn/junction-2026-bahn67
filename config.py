"""Shared parameters. Every tunable number lives here, so an experiment is one changed field
and evaluate.py can log exactly which settings produced which score."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace

HOUR, DAY = 60, 24 * 60


@dataclass(frozen=True)
class Params:
    # Quoting (levels 4+; levels 1-3 always win at list price). Price = list price x quote_mult.
    quote_mult: float = 1.0
    backlog_k: float = 0.0          # levels 4+: quote_mult += backlog_k x (won orders still without a driver); 0 = off
    min_slack_h: float = 0.0        # levels 4+: quote only options with deadline - drive - now >= this many hours; 0 = off (first option only)
    decline_km: float = 0.0         # levels 4+: decline (quote 10x list) when the first leg is longer; 0 = off

    # Normal fee schedule, as multiples of the request's typical fee (referenceFeeCents).
    open_mult: float = 1.0          # opening fee
    raise_per_step: float = 0.10    # added per step (levels 2+; level 1 allows one step)
    raise_every_min: int = HOUR     # minutes between steps
    raise_steps: int = 6            # steps in the schedule, so the cap is open + (steps-1)*raise

    # Steep schedule after deadline_close.
    steep_open_mult: float = 1.5
    steep_raise_per_step: float = 0.25
    steep_every_min: int = 30
    steep_steps: int = 5

    # Ladder: our own raises by reprice, for gigs no driver has booked (0 = off, starter behaviour).
    # Target fee = min(ladder_cap, open_mult + ladder_per_hour * hours since the order was first posted).
    ladder_per_hour: float = 0.0
    ladder_cap: float = 1.5
    tick_min: int = 10              # how often the practice loop wakes up to raise fees

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT = Params()

# Named configurations. DEFAULT reproduces the kit starter; the others are our tuned systems (see LESSONS.md).
PRESETS = {
    "starter": DEFAULT,
    # Level 1: fee ladder by reprice. +€34,186 on l1-a..j (starter -€28,978), worst week 91.1%.
    "l1": Params(open_mult=0.7, ladder_per_hour=0.3, ladder_cap=1.5),
    # Level 8 (the final): price 1.6x list + backlog, decline >500 km, only options with >=8 h slack, fee opens 0.8x.
    # +€79,155 on l8-a..j and +€82,446 on unseen l8x-a..j; 20/20 weeks ranked, worst week 92.0%.
    "l8": Params(quote_mult=1.6, backlog_k=0.01, decline_km=500, min_slack_h=8, open_mult=0.8),
}


def from_overrides(overrides: list[str], base: Params = DEFAULT) -> Params:
    """Parses ["open_mult=0.8", "raise_steps=4"] into a Params, with types from the defaults."""
    types = {f.name: type(getattr(DEFAULT, f.name)) for f in fields(Params)}  # types from the field defaults, not the preset
    changes = {}
    for item in overrides:
        key, _, value = item.partition("=")
        if key not in types:
            raise SystemExit(f"Unknown parameter {key!r}. Known: {', '.join(types)}")
        changes[key] = types[key](value)
    return replace(base, **changes)
