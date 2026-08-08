from epos_v3.application.npc_policy import NPCPolicy
from epos_v3.domain.entities import NPCEntity


def _npc(stats: dict[str, int]) -> NPCEntity:
    return NPCEntity(
        entity_id="alien",
        name="Khepri",
        archetype="scout",
        base_prompt="",
        negative_prompt="",
        role_prompt="scout",
        personality="cautious",
        speech_style="short",
        desires=[], fears=[], goals=[], secrets=[], red_lines=[], intimate_profile="",
        stats=stats,
        location_id="dock",
        is_present=True,
        is_alive=True,
        outfit=[],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
        emotional_state={"fear": 8, "attraction": 8},
    )


def test_npc_reasoning_does_not_require_canonical_skill_names() -> None:
    npc = _npc({"hacking": 4, "piloting": 3})

    intentions = NPCPolicy().reason(npc, "danger")
    actions = {item.action for item in intentions}

    assert "fuggire" in actions
    assert "avvicinarsi_player" in actions
