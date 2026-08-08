"""Thread-safe presentation trace for authoritative dice results."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from epos_v3.application.commit import CommitService
from epos_v3.domain.checks import CheckProposal, CheckType, ResolvedCheck
from epos_v3.domain.world import WorldState


@dataclass(frozen=True, slots=True)
class DiceSnapshot:
    """Immutable player-facing copy of one authoritative resolved check."""

    skill: str | None
    difficulty: int
    pool_size: int
    values: tuple[int, ...]
    successes: int
    outcome: str
    choice: str


class DiceTrace:
    """Store at most one unresolved GUI dice presentation snapshot."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._latest: DiceSnapshot | None = None

    def record(self, resolved: ResolvedCheck) -> None:
        """Record a resolved check without changing or rerolling it."""
        snapshot = DiceSnapshot(
            skill=resolved.proposal.skill,
            difficulty=resolved.proposal.difficulty,
            pool_size=resolved.pool_size,
            values=tuple(resolved.dice.pool),
            successes=resolved.dice.successes,
            outcome=resolved.outcome.value,
            choice=resolved.choice,
        )
        with self._lock:
            self._latest = snapshot

    def pop(self) -> DiceSnapshot | None:
        """Return and clear the latest snapshot atomically."""
        with self._lock:
            snapshot = self._latest
            self._latest = None
            return snapshot


class TracingCommitService(CommitService):
    """Commit service decorator that mirrors resolved rolls to the GUI trace."""

    def __init__(self, trace: DiceTrace) -> None:
        self._trace = trace

    def resolve_check(
        self,
        proposal: CheckProposal,
        state: WorldState,
        choice: str,
    ) -> ResolvedCheck:
        """Resolve once through Python rules and expose that exact result to the GUI."""
        resolved = super().resolve_check(proposal, state, choice)
        if proposal.check_type != CheckType.NO_CHECK:
            self._trace.record(resolved)
        return resolved
