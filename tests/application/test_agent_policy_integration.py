from __future__ import annotations

import pytest

from epos_v3.application.agents import AgentService
from epos_v3.domain.entities import NPCEntity, Player, Relationship
from epos_v3.domain.world import Location, WorldState


def _state() -> WorldState:
    npc = NPCEntity(
        entity_id="observer",
        name="Observer",
        archetype="test",
        base_prompt="",
        negative_prompt="",
        character_lora=[],
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
        location_id="hall",
        is_present=True,
        is_alive=True,
        outfit=[],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
        relationships={"player": Relationship(suspicion=8)},
    )
    return WorldState(
        session_id="s",
        worldpack_id="w",
        turn_number=5,
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
        npcs={"observer": npc},
        locations={"hall": Location(location_id="hall", name="Hall")},
    )


@pytest.mark.asyncio
async def test_agent_service_uses_canonical_policy_for_relationship_driven_initiative() -> None:
    state = _state()

    initiatives = await AgentService().process_agents(state)

    assert initiatives[0]["npc_id"] == "observer"
    assert initiatives[0]["action"] == "osservare_player"
