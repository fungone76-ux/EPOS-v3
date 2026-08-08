from epos_v3.application.validation import ValidationService
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.entities import Player
from epos_v3.domain.world import Location, WorldState


def state() -> WorldState:
    return WorldState(
        session_id="s1", worldpack_id="w1",
        player=Player(entity_id="player", name="Hero", outfit=[], stats={"Sarissa": 1}, inventory=[], location_id="beach", conditions=[], knowledge=[]),
        npcs={}, locations={"beach": Location(location_id="beach", name="Beach")},
        skill_definitions={"Sarissa": "legacy test skill"},
    )


def test_valid_check_proposal() -> None:
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL, skill="Sarissa", difficulty=4,
        stakes={"full_success":"win", "partial_success":"mixed", "failure":"lose", "critical_failure":"disaster"},
    )
    valid, errors = ValidationService().validate_check_proposal(proposal, state())
    assert valid
    assert errors == []


def test_invalid_difficulty_is_reported() -> None:
    proposal = CheckProposal.model_construct(
        check_type=CheckType.CHECK_PROPOSAL, skill="Sarissa", difficulty=10,
        target_ids=[], opposition="none", stakes={
            "full_success":"win", "partial_success":"mixed", "failure":"lose", "critical_failure":"disaster"
        }, triggers=[], description="",
    )
    valid, errors = ValidationService().validate_check_proposal(proposal, state())
    assert not valid
    assert "difficulty 10 not in [1,6]" in errors


def test_scene_rejects_unknown_speaker_and_focus() -> None:
    vst = {
        "dialogue": ["Ghost: boo"],
        "visual": {"focus_character": "luna", "visible_characters": ["player"]},
        "mutations": [], "subjects": [],
    }
    valid, errors = ValidationService().validate_scene(vst, state())
    assert not valid
    assert any("speaker Ghost" in error for error in errors)
    assert "focus luna not in visible characters" in errors


def test_scene_rejects_visual_location_outside_player_location() -> None:
    vst = {
        "mutations": [], "dialogue": [], "subjects": [],
        "location": {"location_id": "office"},
        "visual": {},
    }
    valid, errors = ValidationService().validate_scene(vst, state())
    assert not valid
    assert "visual location office must match player location beach" in errors


def test_scene_rejects_visual_npc_outside_player_location() -> None:
    from epos_v3.domain.entities import NPCEntity

    world = state()
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={"Sarissa": 1}, location_id="office",
        is_present=True, is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    vst = {
        "mutations": [], "dialogue": [],
        "location": {"location_id": "beach"},
        "subjects": [{"entity_id": "luna", "body_state": "fully_nude"}],
        "visual": {},
    }
    valid, errors = ValidationService().validate_scene(vst, world)
    assert not valid
    assert "visual subject luna not present at player location beach" in errors


def test_check_target_must_share_player_location() -> None:
    from epos_v3.domain.entities import NPCEntity

    world = state()
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={"Sarissa": 1}, location_id="office",
        is_present=True, is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="observe Luna",
        target_ids=["luna"],
    )

    valid, errors = ValidationService().validate_check_proposal(proposal, world)

    assert not valid
    assert "target luna not at player location beach" in errors


def test_movement_target_may_be_at_destination_location() -> None:
    from epos_v3.domain.entities import NPCEntity

    world = state()
    world.locations["private_beach"] = Location(
        location_id="private_beach", name="Private Beach"
    )
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="",
        negative_prompt="", role_prompt="", personality="calm", speech_style="plain",
        desires=[], fears=[], goals=[], secrets=[], red_lines=[], intimate_profile="",
        stats={"Sarissa": 1}, location_id="private_beach", is_present=True, is_alive=True,
        outfit=[], conditions=[], knowledge=[], known_secrets=[], false_beliefs=[],
        discoveries=[],
    )
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        target_ids=["luna"],
        destination_location_id="private_beach",
    )

    valid, errors = ValidationService().validate_check_proposal(proposal, world)

    assert valid
    assert errors == []


def test_movement_rejects_unknown_destination() -> None:
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        destination_location_id="missing_place",
    )

    valid, errors = ValidationService().validate_check_proposal(proposal, state())

    assert not valid
    assert "unknown destination: missing_place" in errors
