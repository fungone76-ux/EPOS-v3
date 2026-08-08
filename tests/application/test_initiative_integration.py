from __future__ import annotations

from epos_v3.application.initiative_integration import InitiativeIntegrationService
from epos_v3.domain.entities import NPCEntity
from epos_v3.domain.world import Location, WorldState
from epos_v3.domain.entities import Player


def _npc(entity_id: str, name: str, location_id: str) -> NPCEntity:
    return NPCEntity(
        entity_id=entity_id,
        name=name,
        archetype="test",
        base_prompt="",
        negative_prompt="",
        role_prompt="",
        personality="",
        speech_style="",
        desires=[],
        fears=[],
        goals=[],
        secrets=[],
        red_lines=[],
        intimate_profile="",
        stats={},
        location_id=location_id,
        is_present=True,
        is_alive=True,
        outfit=[],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
    )


def _state() -> WorldState:
    return WorldState(
        session_id="s",
        worldpack_id="w",
        turn_number=3,
        player=Player(
            entity_id="player",
            name="Hero",
            outfit=[],
            stats={},
            inventory=[],
            location_id="hall",
            conditions=[],
            knowledge=[],
        ),
        npcs={
            "actor": _npc("actor", "Actor", "hall"),
            "witness": _npc("witness", "Witness", "hall"),
            "elsewhere": _npc("elsewhere", "Elsewhere", "garden"),
        },
        locations={
            "hall": Location(location_id="hall", name="Hall"),
            "garden": Location(location_id="garden", name="Garden"),
        },
    )


def test_record_initiative_is_remembered_by_actor_and_local_witness_only() -> None:
    state = _state()
    service = InitiativeIntegrationService()
    initiative = {
        "npc_id": "actor",
        "action": "confrontare",
        "reason": "high anger",
        "narration": "Actor si avvicina con tono duro.",
    }

    service.record(state, [initiative])

    assert state.npcs["actor"].short_term_memory[-1].text == initiative["narration"]
    assert state.npcs["witness"].short_term_memory[-1].text == initiative["narration"]
    assert state.npcs["elsewhere"].short_term_memory == []
    assert state.npcs["actor"].perceived_events[-1].type == "npc_initiative"
    assert state.npcs["witness"].perceived_events[-1].type == "npc_initiative"


def test_record_same_initiative_twice_does_not_duplicate_memory() -> None:
    state = _state()
    service = InitiativeIntegrationService()
    initiative = {
        "npc_id": "actor",
        "action": "confrontare",
        "reason": "high anger",
        "narration": "Actor si avvicina con tono duro.",
    }

    service.record(state, [initiative])
    service.record(state, [initiative])

    actor_entries = [m for m in state.npcs["actor"].short_term_memory if m.text == initiative["narration"]]
    witness_entries = [m for m in state.npcs["witness"].short_term_memory if m.text == initiative["narration"]]
    assert len(actor_entries) == 1
    assert len(witness_entries) == 1


def test_compose_appends_npc_initiatives_without_inventing_player_action() -> None:
    service = InitiativeIntegrationService()
    initiatives = [
        {
            "npc_id": "actor",
            "action": "confrontare",
            "reason": "high anger",
            "narration": "Actor ti rivolge la parola con fermezza.",
        }
    ]

    result = service.compose("Osservi la sala.", initiatives)

    assert result == "Osservi la sala.\n\nActor ti rivolge la parola con fermezza."

from pathlib import Path

import pytest

from epos_v3.application.advance_orchestrator import TimeAdvanceOrchestrator
from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

WORLD = Path(__file__).parents[2] / "worldpacks" / "resort_world"


class _Store:
    def __init__(self, state: WorldState) -> None:
        self.state = state

    async def load(self, session_id: str) -> WorldState | None:
        if session_id != self.state.session_id:
            return None
        return self.state.model_copy(deep=True)

    async def save(self, session_id: str, state: WorldState) -> None:
        assert session_id == state.session_id
        self.state = state.model_copy(deep=True)

    async def list_sessions(self) -> list[str]:
        return [self.state.session_id]

    async def delete(self, session_id: str) -> None:
        raise NotImplementedError


class _LLM:
    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        return CheckProposal(check_type=CheckType.NO_CHECK, description="observe")

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        if resolved_outcome == "npc_initiative":
            return "Victoria Hale arretra, chiaramente impaurita."
        return "Osservi ciò che accade intorno a te."

    async def clarify(self, snapshot: str, player_input: str) -> str:
        return ""

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> dict[str, object]:
        return {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}


class _Renderer:
    def is_available(self) -> bool:
        return False

    async def render(self, visual_contract: dict[str, object]) -> str:
        return "unused"


class _Bus:
    async def publish(self, event: object) -> None:
        return None

    def subscribe(self, event_type: type[object], handler: object) -> None:
        return None


@pytest.mark.asyncio
async def test_turn_puts_npc_initiative_in_visible_narration_and_memory() -> None:
    state = WorldpackLoader().load(WORLD, session_id="initiative-turn").world
    state.npcs["victoria"].emotional_state["fear"] = 9
    store = _Store(state)
    service = TurnOrchestrator(_LLM(), _Renderer(), store, _Bus())

    result = await service.play_turn("initiative-turn", "Osservo la stanza")

    assert "Osservi ciò che accade" in result["narration"]
    assert "Victoria Hale arretra" in result["narration"]
    assert any(
        memory.text == "Victoria Hale arretra, chiaramente impaurita."
        for memory in store.state.npcs["victoria"].short_term_memory
    )


@pytest.mark.asyncio
async def test_advance_exposes_narration_and_records_initiative_memory() -> None:
    state = WorldpackLoader().load(WORLD, session_id="initiative-advance").world
    state.npcs["victoria"].emotional_state["fear"] = 9
    store = _Store(state)
    service = TimeAdvanceOrchestrator(store=store, initiative_llm=_LLM())

    result = await service.advance("initiative-advance")

    assert "Victoria Hale arretra" in result["narration"]
    assert any(
        memory.text == "Victoria Hale arretra, chiaramente impaurita."
        for memory in store.state.npcs["victoria"].short_term_memory
    )


@pytest.mark.asyncio
async def test_turn_hides_remote_npc_initiative_from_player_narration() -> None:
    state = WorldpackLoader().load(WORLD, session_id="initiative-remote").world
    state.npcs["luna"].emotional_state["fear"] = 9
    state.npcs["luna"].location_id = "loc_wild_beach"
    state.npcs["luna"].is_present = True
    store = _Store(state)
    service = TurnOrchestrator(_LLM(), _Renderer(), store, _Bus())

    result = await service.play_turn("initiative-remote", "Osservo la lobby")

    assert all(item["npc_id"] != "luna" for item in result["initiatives"])


def test_compose_does_not_duplicate_initiative_equal_to_base_narration() -> None:
    service = InitiativeIntegrationService()
    text = "Luna osserva attentamente la scena."
    initiatives = [
        {
            "npc_id": "luna",
            "action": "osservare",
            "reason": "curiosita",
            "narration": text,
        }
    ]

    result = service.compose(text, initiatives)

    assert result == text
