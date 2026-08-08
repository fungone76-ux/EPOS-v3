"""Worldpack regression tests for the open-ended Azure Crown campaign."""

from pathlib import Path

from epos_v3.infrastructure.worldpack import WorldpackLoader
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay


WORLD = Path("worldpacks/resort_world")


def _load_state():
    return WorldpackLoader().load(WORLD, session_id="test-open-end").world


def _mission_rules() -> dict[str, dict[str, object]]:
    state = _load_state()
    return {
        str(row["id"]): row
        for row in state.gameplay_rules["missions"]
        if isinstance(row, dict)
    }


def test_resort_has_no_fixed_campaign_deadline() -> None:
    """The economic plot may create pressure but must not end the campaign on day seven."""
    rules = _mission_rules()

    assert "deadline" not in rules["mission_resort_future"]


def test_arrival_intro_is_the_only_initial_campaign_mission() -> None:
    """Freeplay and endgame remain gated until the canonical introductions finish."""
    rules = _mission_rules()

    assert rules["mission_resort_arrival"]["reveal"] == "initial"
    assert rules["mission_resort_future"]["reveal"] == "progressive"
    assert rules["mission_four_bonds"]["reveal"] == "progressive"
    assert rules["mission_four_bonds"]["unlock_when"] == {
        "flag": "resort_intro_completed",
        "expected": True,
    }


def test_four_bonds_is_the_campaign_completion_mission() -> None:
    """Campaign completion requires all four distinct consensual adult bonds."""
    rules = _mission_rules()
    mission = rules["mission_four_bonds"]

    assert mission["required_flags"] == [
        "victoria_intimate_bond_complete",
        "stella_intimate_bond_complete",
        "maria_intimate_bond_complete",
        "luna_intimate_bond_complete",
    ]
    assert mission["complete_when_required_flags"] is True
    assert mission["completion_flag"] == "campaign_complete"


def test_four_bonds_completion_is_python_deterministic() -> None:
    """Python, not the LLM, marks the campaign complete when all four bonds exist."""
    state = _load_state()
    state.global_flags["resort_intro_completed"] = True
    for flag in (
        "victoria_intimate_bond_complete",
        "stella_intimate_bond_complete",
        "maria_intimate_bond_complete",
        "luna_intimate_bond_complete",
    ):
        state.global_flags[flag] = True

    WorldpackGameplay().refresh_state_missions(state)

    assert state.global_flags["campaign_complete"] is True
    assert state.missions["mission_four_bonds"].is_completed is True


def test_each_npc_arc_has_an_intermediate_adult_progression_step() -> None:
    """NPC arcs should not jump directly from introduction to final milestone."""
    rules = _mission_rules()

    assert "victoria_private_audit_complete" in rules["mission_victoria_save_resort"]["required_flags"]
    assert "stella_private_rehearsal_complete" in rules["mission_stella_promotion"]["required_flags"]
    assert "maria_private_trust_complete" in rules["mission_maria_stability"]["required_flags"]
    assert "luna_present_choice_complete" in rules["mission_luna_letter"]["required_flags"]
