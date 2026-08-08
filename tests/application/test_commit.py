from epos_v3.application.commit import CommitService
from epos_v3.domain.checks import CheckProposal, CheckType, ResolvedCheck
from epos_v3.domain.dice import DiceResult
from epos_v3.domain.entities import Player
from epos_v3.domain.world import Location, WorldState


def state() -> WorldState:
    return WorldState(
        session_id="s1", worldpack_id="w1",
        player=Player(entity_id="player", name="Hero", outfit=[], stats={}, inventory=[], location_id="beach", conditions=[], knowledge=[]),
        npcs={}, locations={"beach": Location(location_id="beach", name="Beach")},
    )


def test_apply_mutations_uses_deep_copy() -> None:
    original = state()
    resolved = ResolvedCheck(proposal=CheckProposal(check_type=CheckType.NO_CHECK), pool_size=0, dice=DiceResult([]), choice="roll")
    new_state = CommitService().apply_mutations(original, resolved, {"mutations": [{"type": "condition_add", "target_id": "player", "value": "wet"}]})
    assert "wet" in new_state.player.conditions
    assert "wet" not in original.player.conditions
    assert new_state is not original


def test_resolve_no_check_does_not_roll() -> None:
    proposal = CheckProposal(check_type=CheckType.NO_CHECK)
    resolved = CommitService().resolve_check(proposal, state(), "roll")
    assert resolved.pool_size == 0
    assert resolved.outcome.value == "failure"
