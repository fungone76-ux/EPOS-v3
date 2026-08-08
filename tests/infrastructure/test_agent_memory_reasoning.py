from __future__ import annotations

from epos_v3.domain.entities import NPCEntity, Relationship
from epos_v3.domain.events import TurnEvent
from epos_v3.infrastructure.agents.npc_agent import NPCPolicy


def _npc() -> NPCEntity:
    return NPCEntity(
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
        stats={"Sarissa": 2},
        location_id="hall",
        is_present=True,
        is_alive=True,
        outfit=[],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
        relationships={"player": Relationship()},
    )


def test_perceived_relationship_change_influences_future_intention() -> None:
    npc = _npc()
    policy = NPCPolicy()
    policy.perceive(
        npc,
        TurnEvent(
            turn=1,
            type="suspicious_action",
            description="Il giocatore viene visto mentre fruga nei documenti.",
            target_id="player",
            relationship_delta={"suspicion": 8},
            importance=8,
        ),
    )

    intentions = policy.reason(npc, "turno successivo")

    assert intentions[0].action == "osservare_player"
    assert intentions[0].priority >= 8
    assert npc.relationships["player"].suspicion == 8


def test_high_resentment_from_memory_can_drive_confrontation() -> None:
    npc = _npc()
    policy = NPCPolicy()
    policy.perceive(
        npc,
        TurnEvent(
            turn=2,
            type="betrayal",
            description="Il giocatore tradisce una promessa.",
            target_id="player",
            relationship_delta={"resentment": 9},
            importance=9,
        ),
    )

    intentions = policy.reason(npc, "turno successivo")

    assert intentions[0].action == "confrontare_player"
    assert intentions[0].priority == 9
