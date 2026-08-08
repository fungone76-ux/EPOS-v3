from epos_v3.domain.entities import NPCEntity
from epos_v3.domain.events import TurnEvent

def create_test_npc() -> NPCEntity:
    return NPCEntity(
        entity_id="luna",
        name="Luna",
        archetype="companion",
        base_prompt="base",
        negative_prompt="negative",
        character_lora=[],
        role_prompt="role",
        personality="warm",
        speech_style="soft",
        desires=[], fears=[], goals=[], secrets=[], red_lines=[], intimate_profile="",
        stats={"Sarissa": 1, "Dolos": 1, "Eros": 1, "Thumos": 1, "Pontos": 1},
        location_id="beach", is_present=True, is_alive=True, outfit=[], conditions=[],
        knowledge=[], known_secrets=[], false_beliefs=[], discoveries=[],
    )

def test_npc_perceive_updates_emotional_state() -> None:
    npc = create_test_npc()
    event = TurnEvent(turn=5, type="player_threat", description="Mi minaccia")
    npc.perceive(event)
    assert npc.emotional_state["fear"] > 0

def test_npc_reason_generates_intentions() -> None:
    npc = create_test_npc()
    npc.emotional_state["attraction"] = 8
    intentions = npc.reason("Il player mi guarda")
    assert any(i.action == "sedurre" for i in intentions)

def test_relationship_inverse_correlation() -> None:
    npc = create_test_npc()
    npc.update_relationship("player", {"trust": 5}, "Mi ha aiutato")
    npc.update_relationship("player", {"suspicion": 3}, "Ma sembra strano")
    rel = npc.relationships["player"]
    assert rel.trust < 5 or rel.suspicion < 3
