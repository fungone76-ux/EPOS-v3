from pathlib import Path

import pytest

from epos_v3.infrastructure.persistence.json_store import JsonStore
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay
from epos_v3.presentation.gui_controller import GuiController


WORLD = Path(__file__).parents[2] / "worldpacks" / "resort_world"


@pytest.mark.asyncio
async def test_gui_controller_creates_worldpack_session(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "sessions")
    controller = GuiController(
        store=store,
        worldpack_path=WORLD,
        session_id="gui-test",
    )

    state = await controller.initialize()

    assert state.session_id == "gui-test"
    assert state.worldpack_id == "resort_world"


@pytest.mark.asyncio
async def test_gui_controller_state_view_is_player_local(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "sessions")
    controller = GuiController(
        store=store,
        worldpack_path=WORLD,
        session_id="gui-view",
    )
    state = await controller.initialize()

    view = controller.state_view(state)

    assert "Giorno" in view
    assert "Fase" in view
    assert "Posizione" in view
    assert "NPC presenti" in view
    assert "Introduzione" in view


def test_gui_append_uses_qtextcursor_moveoperation_end() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "epos_v3"
        / "presentation"
        / "gui_app.py"
    ).read_text(encoding="utf-8")

    assert "QTextCursor.MoveOperation.End" in source
    assert "textCursor().End" not in source


def test_gui_visual_panel_displays_visual_error() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "epos_v3"
        / "presentation"
        / "gui_app.py"
    ).read_text(encoding="utf-8")

    assert "visual_error" in source
    assert "ERRORE VISUALE" in source


@pytest.mark.asyncio
async def test_gui_state_view_shows_other_npc_locations_and_active_missions(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "sessions")
    controller = GuiController(
        store=store,
        worldpack_path=WORLD,
        session_id="gui-rich-state",
    )
    state = await controller.initialize()
    state.global_flags["resort_intro_completed"] = True
    state.global_flags["resort_intro_active"] = False
    WorldpackGameplay().refresh_state_missions(state)

    view = controller.state_view(state)

    assert "NPC nel mondo" in view
    for npc in state.npcs.values():
        assert npc.name in view
        location = state.locations.get(npc.location_id)
        if location is not None:
            assert location.name in view
    assert "Missioni attive" in view
    assert "Resort future" in view
    assert "Eventi aperti" in view
    assert "A bordo piscina si sta organizzando una prova outfit per un evento VIP." in view
    assert "Puoi osservare, scegliere uno stile" in view


@pytest.mark.asyncio
async def test_gui_state_view_shows_mission_progress(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "sessions")
    controller = GuiController(
        store=store,
        worldpack_path=WORLD,
        session_id="gui-mission-progress",
    )
    state = await controller.initialize()
    state.global_flags["resort_intro_completed"] = True
    state.global_flags["resort_intro_active"] = False
    WorldpackGameplay().refresh_state_missions(state)
    mission = state.missions["mission_resort_future"]
    mission.objectives[0].completed = True

    view = controller.state_view(state)

    assert "1/3" in view


def test_gui_state_panel_is_scrollable_and_uses_rich_text() -> None:
    source = (
        Path(__file__).parents[2]
        / "src"
        / "epos_v3"
        / "presentation"
        / "gui_app.py"
    ).read_text(encoding="utf-8")

    assert "QScrollArea" in source
    assert "setWidgetResizable(True)" in source
    assert "Qt.TextFormat.RichText" in source
