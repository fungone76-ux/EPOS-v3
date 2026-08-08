from __future__ import annotations

from epos_v3.application.visual_canonicalizer import canonicalize_vst
from epos_v3.application.validation import ValidationService
from epos_v3.domain.entities import NPCEntity, Player
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import Location, WorldState


def _state() -> WorldState:
    outfit = [OutfitItem(slot="torso", item_id="dress", name="Dress", coverage=1.0)]
    npc = NPCEntity(
        entity_id="victoria",
        name="Victoria",
        archetype="manager",
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
        location_id="lobby",
        is_present=True,
        is_alive=True,
        outfit=outfit,
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
    )
    return WorldState(
        session_id="s",
        worldpack_id="w",
        player=Player(
            entity_id="player",
            name="Player",
            outfit=[],
            stats={},
            inventory=[],
            location_id="lobby",
            conditions=[],
            knowledge=[],
        ),
        npcs={"victoria": npc},
        locations={"lobby": Location(location_id="lobby", name="Lobby")},
    )


def test_canonicalize_vst_replaces_invalid_location_with_world_state() -> None:
    state = _state()
    vst = {
        "location": "Lobby",
        "subjects": [],
        "mutations": [],
        "dialogue": [],
        "visual": {},
    }

    result = canonicalize_vst(vst, state)

    assert result["location"]["location_id"] == "lobby"
    assert result["location"]["time_of_day"] == state.time_of_day.value
    assert "lighting" in result["location"]


def test_canonicalize_vst_replaces_llm_body_state_before_validation() -> None:
    state = _state()
    vst = {
        "location": {"location_id": "wrong_place"},
        "subjects": [{"entity_id": "victoria", "body_state": "fully_nude"}],
        "mutations": [],
        "dialogue": [],
        "visual": {},
    }

    canonical = canonicalize_vst(vst, state)
    valid, errors = ValidationService().validate_scene(canonical, state)

    assert canonical["location"]["location_id"] == "lobby"
    assert canonical["subjects"][0]["body_state"] == "bottomless"
    assert valid
    assert errors == []


def test_canonicalize_minimal_vst_produces_complete_visual_contract() -> None:
    from epos_v3.infrastructure.visual.vst_models import VisualSemanticTable

    state = _state()
    minimal = {
        "subjects": [{"entity_id": "victoria"}],
        "mutations": [],
        "dialogue": [],
        "visual": {},
    }

    canonical = canonicalize_vst(minimal, state)

    visual_keys = set(VisualSemanticTable.model_fields)
    validated = VisualSemanticTable.model_validate(
        {key: value for key, value in canonical.items() if key in visual_keys}
    )
    assert validated.location.location_id == "lobby"
    assert validated.style.model == "default"
    assert validated.camera.shot_type
    assert validated.lighting.primary
    assert validated.safety.outfit_authoritative is True
    assert validated.subjects[0].entity_id == "victoria"
    assert validated.subjects[0].gender == "ambiguous"


def test_world_visual_compiler_accepts_minimal_llm_vst() -> None:
    from epos_v3.infrastructure.visual.world_compiler import WorldVisualCompiler

    state = _state()
    minimal = {
        "subjects": [{"entity_id": "victoria"}],
        "mutations": [],
        "dialogue": [],
        "visual": {},
    }

    contract = WorldVisualCompiler().compile(minimal, state)

    assert contract["prompt"]
    assert contract["negative_prompt"]
    assert contract["vst"]["location"]["location_id"] == state.player.location_id
