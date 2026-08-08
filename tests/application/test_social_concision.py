from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.domain.checks import CheckProposal, CheckType


def test_direct_social_policy_is_two_sentences() -> None:
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Parlo con Victoria",
        target_ids=["victoria"],
    )
    assert TurnOrchestrator._is_direct_social_input(
        "cosa puoi fare per allietarmi la giornata?",
        proposal,
    )


def test_routine_initiative_is_suppressed_without_target_when_social() -> None:
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Parlo",
        target_ids=[],
    )
    initiative = {
        "npc_id": "victoria",
        "reason": "Goal non soddisfatto: convincere il protagonista a investire",
    }

    assert TurnOrchestrator._suppress_routine_target_initiative(
        initiative,
        proposal,
        brief_social=True,
    )
