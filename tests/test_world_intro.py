"""Tests for deterministic Worldpack intro progression."""

from pathlib import Path

from epos_v3.application.world_intro import WorldIntroService
from epos_v3.infrastructure.worldpack import WorldpackLoader


WORLD = Path("worldpacks/resort_world")


def _state():
    return WorldpackLoader().load(WORLD, session_id="intro-test").world


def test_intro_starts_with_player_presentation_prompt() -> None:
    state = _state()
    intro = WorldIntroService()

    step = intro.current_step(state)

    assert step is not None
    assert step.kind == "player_intro"
    assert step.target_npc_id == "victoria"
    assert "piacere di accogliere" in step.dialogue


def test_first_player_input_stores_presentation_then_introduces_victoria() -> None:
    state = _state()
    intro = WorldIntroService()

    result = intro.resolve(state, "Mi chiamo Alex e sono qui per conoscere il resort.")

    assert result is not None
    assert result.step_id == "victoria"
    assert result.focus_npc_id == "victoria"
    assert state.global_flags["player_intro_text"] == "Mi chiamo Alex e sono qui per conoscere il resort."
    assert state.global_flags["resort_intro_index"] == 2


def test_intro_progresses_one_npc_per_player_input() -> None:
    state = _state()
    intro = WorldIntroService()

    first = intro.resolve(state, "Sono Alex.")
    second = intro.resolve(state, "Piacere Victoria.")
    third = intro.resolve(state, "Piacere Luna.")
    fourth = intro.resolve(state, "Piacere Maria.")

    assert first is not None and first.step_id == "victoria"
    assert second is not None and second.step_id == "luna"
    assert third is not None and third.step_id == "maria"
    assert fourth is not None and fourth.step_id == "stella"
    assert fourth.completed is True
    assert state.global_flags["resort_intro_completed"] is True
    assert state.global_flags["resort_intro_active"] is False
    assert intro.current_step(state) is None


def test_intro_visual_has_only_the_focus_npc_and_never_the_player() -> None:
    state = _state()
    intro = WorldIntroService()

    result = intro.resolve(state, "Sono il nuovo ospite.")

    assert result is not None
    ids = [subject["entity_id"] for subject in result.vst["subjects"]]
    assert ids == ["victoria"]
    assert "player" not in ids
