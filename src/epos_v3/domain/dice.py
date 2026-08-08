"""Authoritative dice mechanics."""

from __future__ import annotations

from enum import StrEnum
import random
from typing import Mapping, Sequence


class OutcomeLevel(StrEnum):
    """The four authoritative outcome levels."""

    CRITICAL_FAILURE = "critical_failure"
    FAILURE = "failure"
    PARTIAL_SUCCESS = "partial_success"
    FULL_SUCCESS = "full_success"


class DiceResult:
    """Immutable dice result resolved by the domain rules."""

    __slots__ = ("pool", "threshold", "successes", "outcome")

    def __init__(self, pool: Sequence[int], threshold: int = 4) -> None:
        """Validate dice and derive successes and outcome."""
        if not 1 <= threshold <= 6:
            raise ValueError("threshold must be in [1, 6]")
        values = tuple(pool)
        if any(not 1 <= die <= 6 for die in values):
            raise ValueError("every die must be in [1, 6]")
        self.pool = values
        self.threshold = threshold
        self.successes = sum(die >= threshold for die in values)
        if values and all(die == 1 for die in values):
            self.outcome = OutcomeLevel.CRITICAL_FAILURE
        elif self.successes == 0:
            self.outcome = OutcomeLevel.FAILURE
        elif self.successes == 1:
            self.outcome = OutcomeLevel.PARTIAL_SUCCESS
        else:
            self.outcome = OutcomeLevel.FULL_SUCCESS


def calculate_pool_size(stats: Mapping[str, int], skills: Sequence[str]) -> int:
    """Calculate the pool as one base die plus selected skill ratings."""
    if not skills:
        return 1
    total = 1
    for skill in skills:
        rating = stats.get(skill, 0)
        if not 0 <= rating <= 3:
            raise ValueError(f"invalid skill rating for {skill!r}: {rating}")
        total += rating
    return total


def roll_pool(pool_size: int, threshold: int = 4, rng: random.Random | None = None) -> DiceResult:
    """Roll a pool of d6 and resolve its authoritative outcome."""
    if pool_size < 0:
        raise ValueError("pool_size must be non-negative")
    generator = rng if rng is not None else random.SystemRandom()
    pool = [generator.randint(1, 6) for _ in range(pool_size)]
    return DiceResult(pool, threshold)
