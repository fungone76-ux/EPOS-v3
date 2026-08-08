"""Tests for dynamic conversation goals and concrete-answer narration context."""

from __future__ import annotations

import json
from pathlib import Path

from epos_v3.application.conversation_guidance import ConversationGoal, conversation_goal_for
from epos_v3.application.narration_context import build_narration_snapshot
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.infrastructure.llm.narration_contract import NARRATION_INSTRUCTIONS
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


def test_direct_factual_question_uses_inform_goal() -> None:
    """Direct factual questions must push the NPC toward concrete information."""
    assert conversation_goal_for("Che stanze ci sono da visitare?") is ConversationGoal.INFORM
    assert conversation_goal_for("Raccontami la leggenda di questo ritratto, la sai?") is ConversationGoal.INFORM


def test_decision_request_uses_decision_goal() -> None:
    """Requests for a choice should move the exchange toward a decision."""
    assert conversation_goal_for("Allora, accetti la mia proposta?") is ConversationGoal.SEEK_DECISION


def test_narration_snapshot_contains_concrete_world_reference_and_npc_knowledge() -> None:
    """The narrator receives enough grounded data to answer concrete questions."""
    loader = WorldpackLoader()
    state = loader.load(Path("worldpacks/resort_world"), session_id="conversation-test")
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Chiede quali luoghi si possono visitare.",
        target_ids=["victoria"],
    )

    snapshot = json.loads(
        build_narration_snapshot(
            state,
            proposal,
            player_input="Che stanze ci sono da visitare?",
            direct_social=True,
        )
    )

    assert snapshot["conversation_directive"]["goal"] == "inform"
    assert "concrete facts" in snapshot["conversation_directive"]["requirements"].lower()
    assert len(snapshot["world_reference"]["locations"]) >= 2
    victoria = snapshot["local_npcs"]["victoria"]
    assert victoria["knowledge"]
    assert isinstance(victoria["disclosure_policy"], str)


def test_direct_answer_policy_forbids_evasive_mystery_substitution() -> None:
    """A direct question must not be answered with generic mystery or metaphor."""
    loader = WorldpackLoader()
    state = loader.load(Path("worldpacks/resort_world"), session_id="anti-evasion-test")
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Chiede informazioni concrete.",
        target_ids=["victoria"],
    )

    snapshot = json.loads(
        build_narration_snapshot(
            state,
            proposal,
            player_input="Cosa sai di questa storia?",
            direct_social=True,
        )
    )

    requirements = snapshot["conversation_directive"]["requirements"].lower()
    assert "do not substitute mystery" in requirements
    assert "say exactly what is unknown" in requirements


def test_provider_contract_prioritizes_dynamic_conversation_goal() -> None:
    """Every provider must explicitly honor the deterministic conversation directive."""
    lowered = NARRATION_INSTRUCTIONS.lower()
    assert "conversation_directive" in lowered
    assert "conversation_objective" in lowered
    assert "direct question" in lowered
    assert "mystery" in lowered
