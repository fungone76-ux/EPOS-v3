from __future__ import annotations

from pathlib import Path

import pytest

from epos_v3.application.advance_orchestrator import TimeAdvanceOrchestrator
from epos_v3.domain.world import WorldState
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

WORLD = Path(__file__).parents[2] / "worldpacks" / "resort_world"


class MemoryStore:
    def __init__(self, state: WorldState) -> None:
        self.state = state
        self.save_count = 0

    async def load(self, session_id: str) -> WorldState | None:
        assert session_id == self.state.session_id
        return self.state.model_copy(deep=True)

    async def save(self, session_id: str, state: WorldState) -> None:
        assert session_id == state.session_id
        self.state = state.model_copy(deep=True)
        self.save_count += 1

    async def list_sessions(self) -> list[str]:
        return [self.state.session_id]

    async def delete(self, session_id: str) -> None:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_explicit_advance_updates_clock_rules_agents_and_saves_once() -> None:
    state = WorldpackLoader().load(WORLD, session_id="advance").world
    state.npcs["victoria"].emotional_state["fear"] = 9
    store = MemoryStore(state)
    service = TimeAdvanceOrchestrator(store=store, world_rules=WorldpackGameplay())

    result = await service.advance("advance")

    assert result["day"] == 1
    assert result["phase"] == "pomeriggio"
    assert result["turn_number"] == 1
    assert store.state.world_phase == "pomeriggio"
    assert store.save_count == 1
    assert any(item["npc_id"] == "victoria" for item in result["initiatives"])
    assert all(
        event.get("trigger", {}).get("player_request") is not True
        for event in result["available_events"]
    )


@pytest.mark.asyncio
async def test_time_advance_agent_perception_is_not_fake_player_action() -> None:
    state = WorldpackLoader().load(WORLD, session_id="advance").world
    state.npcs["victoria"].last_player_action = "Il player saluta Victoria"
    store = MemoryStore(state)
    service = TimeAdvanceOrchestrator(store=store, world_rules=WorldpackGameplay())

    await service.advance("advance")

    perceived_events = store.state.npcs["victoria"].perceived_events
    time_events = [event for event in perceived_events if event.type == "time_advanced"]
    assert len(time_events) == 1
    assert "pomeriggio" in time_events[0].description
    assert all(
        not (event.type == "player_action" and event.description == "Il player saluta Victoria")
        for event in perceived_events
    )


@pytest.mark.asyncio
async def test_advance_missing_session_does_not_save() -> None:
    state = WorldpackLoader().load(WORLD, session_id="advance").world
    store = MemoryStore(state)

    async def missing(_: str) -> WorldState | None:
        return None

    store.load = missing  # type: ignore[method-assign]
    service = TimeAdvanceOrchestrator(store=store, world_rules=WorldpackGameplay())

    with pytest.raises(ValueError, match="Session not found"):
        await service.advance("missing")

    assert store.save_count == 0


class NarrativeLLM:
    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        assert resolved_outcome == "npc_initiative"
        return "Victoria Hale si irrigidisce e arretra, cercando una via d'uscita."


@pytest.mark.asyncio
async def test_advance_can_return_contextual_narration_for_npc_initiatives() -> None:
    state = WorldpackLoader().load(WORLD, session_id="advance-narrated").world
    state.npcs["victoria"].emotional_state["fear"] = 9
    store = MemoryStore(state)
    service = TimeAdvanceOrchestrator(
        store=store,
        world_rules=WorldpackGameplay(),
        initiative_llm=NarrativeLLM(),
    )

    result = await service.advance("advance-narrated")

    victoria = next(item for item in result["initiatives"] if item["npc_id"] == "victoria")
    assert victoria["action"] == "fuggire"
    assert "via d'uscita" in victoria["narration"]
