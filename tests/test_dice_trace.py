"""Tests for GUI dice tracing without rerolling in the presentation layer."""

from types import SimpleNamespace
from unittest.mock import patch

from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.dice import DiceResult
from epos_v3.presentation.dice_trace import DiceTrace, TracingCommitService


def test_tracing_commit_service_records_authoritative_roll() -> None:
    """The GUI trace must expose exactly the dice rolled by Python once."""
    trace = DiceTrace()
    service = TracingCommitService(trace)
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="Convincere Victoria",
        skill="carisma",
        difficulty=4,
    )
    state = SimpleNamespace(player=SimpleNamespace(stats={"carisma": 3}))

    authoritative = DiceResult([2, 5, 6, 3], 4)
    with patch("epos_v3.application.commit.roll_pool", return_value=authoritative) as roller:
        resolved = service.resolve_check(proposal, state, "roll")  # type: ignore[arg-type]

    snapshot = trace.pop()
    assert roller.call_count == 1
    assert resolved.dice.pool == (2, 5, 6, 3)
    assert snapshot is not None
    assert snapshot.skill == "carisma"
    assert snapshot.difficulty == 4
    assert snapshot.pool_size == 4
    assert snapshot.values == (2, 5, 6, 3)
    assert snapshot.successes == 2
    assert snapshot.outcome == "full_success"
    assert snapshot.choice == "roll"
    assert trace.pop() is None


def test_no_check_is_not_exposed_as_a_dice_roll() -> None:
    """Narrative no-check turns must not display a fake dice animation."""
    trace = DiceTrace()
    service = TracingCommitService(trace)
    proposal = CheckProposal(check_type=CheckType.NO_CHECK, description="Guardo il mare")
    state = SimpleNamespace(player=SimpleNamespace(stats={}))

    service.resolve_check(proposal, state, "safe")  # type: ignore[arg-type]

    assert trace.pop() is None
