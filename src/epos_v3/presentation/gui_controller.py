"""Presentation controller shared by the optional Qt GUI."""

from __future__ import annotations

from html import escape
from pathlib import Path

from epos_v3.application.advance_orchestrator import TimeAdvanceOrchestrator
from epos_v3.domain.missions import Mission
from epos_v3.domain.world import WorldState
from epos_v3.infrastructure.persistence.json_store import JsonStore
from epos_v3.infrastructure.worldpack import WorldpackLoader
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay

from .app_factory import create_default_orchestrator


class GuiController:
    """Coordinate GUI actions without depending on Qt widgets."""

    def __init__(
        self,
        *,
        store: JsonStore,
        worldpack_path: Path,
        session_id: str,
    ) -> None:
        """Create a GUI controller for one session and Worldpack."""
        self.store = store
        self.worldpack_path = worldpack_path
        self.session_id = session_id
        self.orchestrator = create_default_orchestrator(store)

    async def initialize(self) -> WorldState:
        """Load an existing session or create it from the configured Worldpack."""
        state = await self.store.load(self.session_id)
        if state is not None:
            return state
        state = WorldpackLoader().load(
            self.worldpack_path,
            session_id=self.session_id,
        ).world
        await self.store.save(self.session_id, state)
        return state

    async def play(self, text: str) -> dict[str, object]:
        """Play one normal turn."""
        return await self.orchestrator.play_turn(self.session_id, text)

    async def advance(self) -> dict[str, object]:
        """Advance world time only after explicit GUI input."""
        service = TimeAdvanceOrchestrator(
            store=self.store,
            world_rules=self.orchestrator.world_rules,
            agent_service=self.orchestrator.agent_service,
        )
        return await service.advance(self.session_id)

    async def resume(self) -> dict[str, object]:
        """Resume a saved post-roll checkpoint."""
        return await self.orchestrator.resume_turn(self.session_id)

    async def state(self) -> WorldState:
        """Return the latest persisted state."""
        state = await self.store.load(self.session_id)
        if state is None:
            raise ValueError(f"Session not found: {self.session_id}")
        return state

    @staticmethod
    def state_view(state: WorldState) -> str:
        """Build a rich, player-facing situation panel for the desktop GUI."""
        location = state.locations.get(state.player.location_id)
        location_name = location.name if location is not None else state.player.location_id
        present_npc_rows, world_npc_rows = GuiController._npc_rows(state)
        mission_rows = GuiController._mission_rows(state)
        event_rows = GuiController._event_rows(state)
        skill_rows = [
            f"<b>{escape(GuiController._label(name))}</b> {state.player.stats.get(name, 0)}"
            for name in state.skill_definitions
        ]
        return "".join(
            [
                '<div style="line-height:1.35">',
                '<div style="font-size:17px;font-weight:700;color:#ffffff">',
                f"📍 Posizione: {escape(location_name)}",
                "</div>",
                '<div style="color:#aab2c0;margin-top:2px">',
                f"Giorno {state.day} · Fase {escape(state.world_phase.capitalize())} · Turno {state.turn_number}",
                "</div>",
                GuiController._section("NPC presenti", present_npc_rows),
                GuiController._section("NPC nel mondo", world_npc_rows),
                GuiController._section("Missioni attive", mission_rows),
                GuiController._section("Eventi aperti", event_rows),
                GuiController._section("Skill", skill_rows, compact=True),
                "</div>",
            ]
        )

    @staticmethod
    def _npc_rows(state: WorldState) -> tuple[list[str], list[str]]:
        """Return local NPCs and remote NPC location rows separately."""
        present: list[str] = []
        remote: list[str] = []
        for npc in state.npcs.values():
            if not npc.is_alive:
                continue
            location = state.locations.get(npc.location_id)
            location_name = location.name if location is not None else npc.location_id
            is_here = npc.is_present and npc.location_id == state.player.location_id
            if is_here:
                present.append(
                    '<span style="color:#79d58a">●</span> '
                    f"<b>{escape(npc.name)}</b>"
                )
                continue
            remote.append(
                f"→ <b>{escape(npc.name)}</b>"
                f'<br><span style="color:#aab2c0">{escape(location_name)}</span>'
            )
        present.sort(key=str.casefold)
        remote.sort(key=str.casefold)
        return present or ["Nessuno con te"], remote or ["Nessun altro NPC localizzato"]

    @staticmethod
    def _mission_rows(state: WorldState) -> list[str]:
        """Return active mission summaries with objective progress and deadlines."""
        rules = {
            str(row.get("id")): row
            for row in state.gameplay_rules.get("missions", [])
            if isinstance(row, dict)
        }
        active = [mission for mission in state.missions.values() if mission.is_active]
        rows: list[str] = []
        for mission in active:
            completed = sum(1 for objective in mission.objectives if objective.completed)
            total = len(mission.objectives)
            progress = f"{completed}/{total}" if total else "attiva"
            row = rules.get(mission.mission_id, {})
            deadline = GuiController._deadline(row.get("deadline"))
            suffix = f" · {deadline}" if deadline else ""
            rows.append(
                f"<b>{escape(GuiController._mission_title(mission))}</b>"
                f'<br><span style="color:#aab2c0">{progress} obiettivi{escape(suffix)}</span>'
            )
        return rows or ["Nessuna missione attiva"]

    @staticmethod
    def _event_rows(state: WorldState) -> list[str]:
        """Return clock/trigger-valid events anywhere in the known world."""
        gameplay = WorldpackGameplay()
        found: dict[str, dict[str, object]] = {}
        for location_id in state.locations:
            probe = state.model_copy(deep=True)
            probe.player.location_id = location_id
            for event in gameplay.available_state_events(probe):
                event_id = event.get("id")
                if isinstance(event_id, str):
                    found[event_id] = event
        rows: list[str] = []
        for event in found.values():
            title = event.get("title")
            event_id = event.get("id")
            display = title if isinstance(title, str) and title else str(event_id or "Evento")
            location_id = event.get("location_id")
            location_name = ""
            if isinstance(location_id, str):
                location = state.locations.get(location_id)
                location_name = location.name if location is not None else location_id
            here = location_id == state.player.location_id
            marker = '<span style="color:#79d58a">● QUI</span> ' if here else ""
            place = (
                f'<br><span style="color:#aab2c0">{escape(location_name)}</span>'
                if location_name
                else ""
            )
            summary = event.get("summary")
            summary_line = (
                f'<br><span style="color:#d7dde8">{escape(str(summary))}</span>'
                if isinstance(summary, str) and summary.strip()
                else ""
            )
            player_hook = event.get("player_hook")
            hook_line = (
                f'<br><span style="color:#8fb7ff">{escape(str(player_hook))}</span>'
                if isinstance(player_hook, str) and player_hook.strip()
                else ""
            )
            rows.append(f"{marker}<b>{escape(display)}</b>{place}{summary_line}{hook_line}")
        return rows or ["Nessun evento aperto in questa fase"]

    @staticmethod
    def _section(title: str, rows: list[str], *, compact: bool = False) -> str:
        """Render one compact rich-text section."""
        spacing = "4px" if compact else "7px"
        body = f'<br><div style="margin-top:{spacing}"></div>'.join(rows)
        return (
            '<div style="margin-top:18px;color:#7fa8d8;font-size:13px;font-weight:700">'
            f"{escape(title)}</div>"
            f'<div style="margin-top:7px">{body}</div>'
        )

    @staticmethod
    def _mission_title(mission: Mission) -> str:
        """Return a readable title even when old Worldpacks only provide an id."""
        title = mission.title
        if title and title != mission.mission_id:
            return title
        return GuiController._label(mission.mission_id.removeprefix("mission_"))

    @staticmethod
    def _deadline(value: object) -> str:
        """Render an authored mission deadline when present."""
        if not isinstance(value, dict):
            return ""
        day = value.get("day")
        phase = value.get("phase")
        if isinstance(day, int) and isinstance(phase, str):
            return f"scadenza G{day} {phase}"
        return ""

    @staticmethod
    def _label(identifier: str) -> str:
        """Convert snake_case identifiers into lightweight display labels."""
        return identifier.replace("_", " ").strip().capitalize()
