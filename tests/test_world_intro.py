"""Tests for deterministic Worldpack intro progression."""

from pathlib import Path

from epos_v3.application.world_intro import WorldIntroService
from epos_v3.infrastructure.worldpack import WorldpackLoader


WORLD = Path("worldpacks/resort_world")


def _state():
    return WorldpackLoader().load(WORLD, session_id="intro-test").world


def test_intro_starts_with_player_presentation() -> None:
    state = _state()
    intro = WorldIntroService()

    step = intro.current_step(state)

    assert step is not None
    assert step.kind == "player_intro"
    assert step.target_npc_id == "victoria"


def test_intro_progresses_one_step_per_player_input() -> None:
    state = _state()
    intro = WorldIntroService()

    result = intro.resolve(state, "Mi chiamo Alex e sono qui per conoscere il resort.")
    assert result is not None
    assert result.step_id == "player_intro"
    assert state.global_flags["player_intro_text"] == "Mi chiamo Alex e sono qui per conoscere il resort."
    assert state.global_flags["resort_intro_index"] == 1

    result = intro.resolve(state, "Piacere, Victoria.")
    assert result is not None
    assert result.step_id == "victoria"
    assert result.focus_npc_id == "victoria"
    assert state.global_flags["resort_intro_index"] == 2

    result = intro.resolve(state, "Piacere Luna.")
    assert result is not None
    assert result.step_id == "luna"
    assert result.focus_npc_id == "luna"


def test_intro_completes_only_after_stella() -> None:
    state = _state()
    intro = WorldIntroService()

    for text in (
        "Sono il nuovo ospite.",
        "Piacere Victoria.",
        "Piacere Luna.",
        "Piacere Maria.",
        "Piacere Stella.",
    ):
        result = intro.resolve(state, text)
        assert result is not None

    assert state.global_flags["resort_intro_completed"] is True
    assert state.global_flags["resort_intro_active"] is False
    assert intro.current_step(state) is None


def test_intro_visual_has_only_the_focus_npc_and_never_the_player() -> None:
    state = _state()
    intro = WorldIntroService()

    intro.resolve(state, "Sono il nuovo ospite.")
    result = intro.resolve(state, "Piacere Victoria.")

    assert result is not None
    ids = [subject["entity_id"] for subject in result.vst["subjects"]]
    assert ids == ["victoria"]
    assert "player" not in ids
