from __future__ import annotations

from epos_v3.application.validation import ValidationService
from epos_v3.domain.entities import NPCEntity, Player, Relationship
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import Location, WorldState


def _state() -> WorldState:
    outfit = [OutfitItem(slot="torso", item_id="shirt", name="Shirt")]
    player = Player(
        entity_id="player", name="Player", outfit=outfit, stats={"sarissa": 1},
        inventory=[], location_id="hall", conditions=[], knowledge=[],
    )
    npc = NPCEntity(
        entity_id="npc", name="NPC", archetype="guest", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={"Sarissa": 1}, location_id="hall",
        is_present=True, is_alive=True, outfit=outfit, conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[], relationships={"player": Relationship()},
    )
    return WorldState(
        session_id="s", worldpack_id="w", player=player, npcs={"npc": npc},
        locations={"hall": Location(location_id="hall", name="Hall")},
    )


def test_relationship_delta_accepts_only_canonical_integer_dimensions() -> None:
    state = _state()
    validator = ValidationService()

    ok, errors = validator.validate_scene(
        {"mutations": [{"type": "relationship_delta", "target_id": "npc", "value": {"trust": 2, "suspicion": -1}}]},
        state,
    )
    assert ok is True
    assert errors == []

    ok, errors = validator.validate_scene(
        {"mutations": [{"type": "relationship_delta", "target_id": "npc", "value": {"jealousy": 2}}]},
        state,
    )
    assert ok is False
    assert any("unknown relationship dimension: jealousy" in error for error in errors)

    ok, errors = validator.validate_scene(
        {"mutations": [{"type": "relationship_delta", "target_id": "npc", "value": {"trust": "a lot"}}]},
        state,
    )
    assert ok is False
    assert any("relationship delta trust must be an integer" in error for error in errors)


def test_relationship_delta_requires_existing_npc_and_object_value() -> None:
    state = _state()
    validator = ValidationService()

    ok, errors = validator.validate_scene(
        {"mutations": [{"type": "relationship_delta", "target_id": "missing", "value": {"trust": 1}}]},
        state,
    )
    assert ok is False
    assert any("unknown relationship target: missing" in error for error in errors)

    ok, errors = validator.validate_scene(
        {"mutations": [{"type": "relationship_delta", "target_id": "npc", "value": 3}]},
        state,
    )
    assert ok is False
    assert any("relationship_delta value must be an object" in error for error in errors)
