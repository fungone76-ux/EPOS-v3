"""Regression tests for gameplay gating while an authored intro is active."""

from pathlib import Path

import pytest

from epos_v3.application.advance_orchestrator import TimeAdvanceOrchestrator
from epos_v3.application.world_intro import WorldIntroService
from epos_v3.domain.world import WorldState
from epos_v3.infrastructure.worldpack import WorldpackLoader
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay


WORLD = Path("worldpacks/resort_world")


class MemoryStore:
    def __init__(self, state: WorldState) -> None:
        self.state = state

    async def load(self, session_id: str) -> WorldState | None:
        return self.state if session_id == self.state.session_id else None

    async def save(self, session_id: str, state: WorldState) -> None:
        assert session_id == self.state.session_id
        self.state = state

    async def list_sessions(self) -> list[str]:
        return [self.state.session_id]

    async def delete(self, session_id: str) -> None:
        if session_id == self.state.session_id:
            raise NotImplementedError


def _state() -> WorldState:
    state = WorldpackLoader().load(WORLD, session_id="intro-gate").world
    WorldIntroService().initialise(state)
    return state


def test_events_are_hidden_during_intro() -> None:
    state = _state()

    assert WorldpackGameplay().available_state_events(state) == []


@pytest.mark.asyncio
async def test_time_cannot_advance_during_intro() -> None:
    state = _state()
    store = MemoryStore(state)

    result = await TimeAdvanceOrchestrator(store=store, world_rules=WorldpackGameplay()).advance(
        state.session_id
    )

    assert result["blocked"] is True
    assert result["reason"] == "intro_active"
    assert store.state.day == 1
    assert store.state.world_phase == state.world_phase
    assert store.state.turn_number == state.turn_number
