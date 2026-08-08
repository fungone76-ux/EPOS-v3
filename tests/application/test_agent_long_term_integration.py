from __future__ import annotations

from pathlib import Path

import pytest

from epos_v3.application.agents import AgentService
from epos_v3.infrastructure.memory.provider import InMemoryLongTermMemoryProvider
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

WORLD = Path(__file__).parents[2] / "worldpacks" / "resort_world"


@pytest.mark.asyncio
async def test_agent_cycle_persists_and_recalls_long_term_memory() -> None:
    state = WorldpackLoader().load(WORLD, session_id="memory-integration").world
    provider = InMemoryLongTermMemoryProvider()
    service = AgentService(memory_provider=provider)
    npc = state.npcs["victoria"]
    npc.last_player_action = "Il giocatore aiuta Victoria con il debito"

    await service.process_agents(state)

    store = provider.for_npc(state.session_id, npc.entity_id)
    recalled = store.recall("aiuta debito", n=5)
    assert "Il giocatore aiuta Victoria con il debito" in recalled
