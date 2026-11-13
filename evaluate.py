"""Small score helpers used when comparing practice runs."""
from __future__ import annotations

from spread.types import Score


def margin_euros(score: Score) -> float:
    """Return a score's margin in game euros."""
    return score["marginCents"] / 100


def is_ranked(score: Score) -> bool:
    """Return whether the score meets the challenge delivery minimum."""
    return bool(score["ranked"])
