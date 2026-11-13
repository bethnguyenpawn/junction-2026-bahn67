"""Shared parameters. Every tunable number lives here, so an experiment is one changed field
and evaluate.py can log exactly which settings produced which score."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace

HOUR, DAY = 60, 24 * 60


@dataclass(frozen=True)
class Params:
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


def from_overrides(overrides: list[str], base: Params = DEFAULT) -> Params:
    """Parses ["open_mult=0.8", "raise_steps=4"] into a Params, with types from the defaults."""
    types = {f.name: type(getattr(base, f.name)) for f in fields(base)}
    changes = {}
    for item in overrides:
        key, _, value = item.partition("=")
        if key not in types:
            raise SystemExit(f"Unknown parameter {key!r}. Known: {', '.join(types)}")
        changes[key] = types[key](value)
    return replace(base, **changes)
