"""Regression tests for the Crimson Velvet 1897 Worldpack."""
from pathlib import Path

from epos_v3.application.world_intro import WorldIntroService
from epos_v3.infrastructure.worldpack import WorldpackLoader
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay

WORLD = Path("worldpacks/crimson_velvet_1897")


def _state():
    return WorldpackLoader().load(WORLD, session_id="crimson-test").world


def test_world_loads_with_four_canonical_adult_women() -> None:
    state = _state()
    assert state.worldpack_id == "crimson_velvet_1897"
    assert set(state.npcs) == {"victoria", "stella", "maria", "luna"}
    assert all(npc.visual_gender == "female" for npc in state.npcs.values())


def test_world_is_open_ended_and_has_no_deadline() -> None:
    state = _state()
    clock = state.gameplay_rules["clock"]
    assert isinstance(clock, dict)
    assert clock["open_end"] is True
    for row in state.gameplay_rules["missions"]:
        if isinstance(row, dict):
            assert "deadline" not in row


def test_intro_order_is_victoria_luna_maria_stella_after_player_input() -> None:
    state = _state()
    intro = WorldIntroService()
    assert intro.current_step(state).kind == "player_intro"  # type: ignore[union-attr]

    expected = ["victoria", "luna", "maria", "stella"]
    seen: list[str] = []
    for text in ("Mi presento.", "Piacere Luna.", "Piacere Maria.", "Piacere Stella."):
        result = intro.resolve(state, text)
        assert result is not None
        seen.append(result.focus_npc_id)

    assert seen == expected
    assert state.global_flags["resort_intro_completed"] is True
    assert state.global_flags["resort_intro_active"] is False


def test_final_mission_requires_main_plot_and_four_personal_bonds() -> None:
    state = _state()
    rules = {
        str(row["id"]): row
        for row in state.gameplay_rules["missions"]
        if isinstance(row, dict)
    }
    final = rules["mission_crimson_legacy"]
    assert final["required_flags"] == [
        "crimson_fate_resolved",
        "victoria_bond_complete",
        "stella_bond_complete",
        "maria_bond_complete",
        "luna_bond_complete",
    ]
    assert final["complete_when_required_flags"] is True
    assert final["completion_flag"] == "campaign_complete"


def test_events_are_hidden_during_intro() -> None:
    state = _state()
    WorldIntroService().initialise(state)
    gameplay = WorldpackGameplay()
    assert gameplay.available_state_events(state) == []


def test_each_npc_has_a_distinct_personal_mission() -> None:
    state = _state()
    assert {
        "mission_victoria_house",
        "mission_stella_stage",
        "mission_maria_letters",
        "mission_luna_smugglers",
    }.issubset(state.missions)
