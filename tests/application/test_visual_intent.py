from epos_v3.application.visual_intent import apply_visual_intent
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.entities import NPCEntity, Player
from epos_v3.domain.world import Location, WorldState


def _state() -> WorldState:
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
        outfit=[],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
    )
    state = WorldState(
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
    state.rendering_config["pose_library"] = {
        "default": [
            {"id": "seated", "prompt": "seated comfortably in a lounge chair", "tags": ["seated"]},
            {"id": "leaning", "prompt": "leaning casually against a nearby surface", "tags": ["leaning"]},
        ],
        "focus": {
            "legs": [
                {"id": "legs_crossed", "prompt": "seated with legs crossed", "tags": ["seated", "crossed legs"]},
            ],
            "feet": [
                {"id": "feet_visible", "prompt": "seated with both feet visible", "tags": ["seated"]},
            ],
            "buttocks": [
                {"id": "rear", "prompt": "rear three-quarter stance", "tags": ["rear three quarter"]},
            ],
            "hips": [{"id": "hips", "prompt": "weight shifted to one hip", "tags": ["hip shift"]}],
            "back": [{"id": "back", "prompt": "torso turned away", "tags": ["rear view"]}],
            "chest": [{"id": "chest", "prompt": "upright upper body posture", "tags": ["upright posture"]}],
            "hands": [{"id": "hands", "prompt": "hands naturally visible", "tags": ["hands visible"]}],
            "face": [{"id": "face", "prompt": "neutral head position", "tags": ["head visible"]}],
            "eyes": [{"id": "eyes", "prompt": "eyes unobstructed", "tags": ["eyes unobstructed"]}],
        },
        "actions": {
            "shoe_removal": [
                {"id": "shoe", "prompt": "seated, removing one high heel, one leg extended", "tags": ["seated", "removing high heel", "one leg extended"]},
            ]
        },
    }
    return state


def test_apply_visual_intent_infers_leg_focus_and_crossed_pose() -> None:
    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Parlo con Victoria",
        target_ids=["victoria"],
    )
    vst = {
        "subjects": [{"entity_id": "victoria", "pose": "", "pose_tags": []}],
        "camera": {},
    }

    result = apply_visual_intent(
        vst,
        state,
        proposal,
        "cosa mi consigli? le chiedo guardando le sue gambe",
    )

    assert result["visual_focus"]["target_region"] == "legs"
    assert "legs crossed" in result["subjects"][0]["pose"]
    assert "crossed legs" in result["subjects"][0]["pose_tags"]


def test_apply_visual_intent_adds_pose_variety_when_focus_is_absent() -> None:
    state = _state()
    proposal = CheckProposal(check_type=CheckType.NO_CHECK, description="Parlo", target_ids=["victoria"])
    vst = {"subjects": [{"entity_id": "victoria", "pose": "", "pose_tags": []}]}

    result = apply_visual_intent(vst, state, proposal, "parlo con Victoria")

    assert result["subjects"][0]["pose"]


def test_leg_focus_is_valid_for_visual_schema() -> None:
    from epos_v3.infrastructure.visual.vst_models import VisualSemanticTable

    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Parlo con Victoria",
        target_ids=["victoria"],
    )
    vst = {
        "scene_id": "s",
        "location": {
            "location_id": "lobby",
            "time_of_day": "morning",
            "lighting": "natural",
            "atmosphere": "quiet",
            "environment_tags": [],
        },
        "subjects": [
            {
                "entity_id": "victoria",
                "role": "focus",
                "gender": "female",
                "pose": "standing",
                "pose_tags": [],
                "body_state": "fully_nude",
                "outfit_visible": [],
                "skin_visible": [],
                "expression": "",
                "gaze": "",
                "focal": True,
                "distance_from_camera": "medium",
                "position_relative_to_focus": "front",
            }
        ],
        "action": {
            "type": "dialogue",
            "description": "conversation",
            "interaction": "conversation",
            "intensity": "neutral",
            "narrative_moment": "",
        },
        "visual_focus": None,
        "camera": {
            "shot_type": "medium_shot",
            "angle": "eye_level",
            "orientation": "front",
            "focus": "victoria",
            "depth_of_field": "shallow",
            "background_blur": True,
            "rule_of_thirds": True,
        },
        "lighting": {"primary": "soft", "secondary": "", "rim_light": "", "shadows": ""},
        "style": {"art_style": "cinematic", "rendering": "detailed", "color_palette": "warm", "mood": "quiet", "lora": [], "model": "default"},
        "safety": {"nudity_level": "none", "explicit_tags": False, "policy_compliant": True, "outfit_authoritative": True},
    }

    result = apply_visual_intent(vst, state, proposal, "le dico guardandole le gambe")
    validated = VisualSemanticTable.model_validate(result)

    assert validated.visual_focus is not None
    assert validated.visual_focus.target_region == "legs"
    assert "include legs clearly in frame" in validated.camera.framing_requirements
    assert validated.camera.shot_type == "medium_full_shot"


def test_shoe_removal_becomes_transient_visual_action() -> None:
    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Parlo con Victoria",
        target_ids=["victoria"],
    )
    vst = {
        "subjects": [{"entity_id": "victoria", "pose": "standing", "pose_tags": []}],
        "camera": {},
        "action": {"description": "conversation", "interaction": "conversation"},
    }

    result = apply_visual_intent(
        vst,
        state,
        proposal,
        "le dico mentre lei si toglie le scarpe",
    )

    assert result["visual_focus"]["target_region"] == "feet"
    assert result["subjects"][0]["pose"] == "seated, removing one high heel, one leg extended"
    assert result["action"]["description"] == "removing one high heel during conversation"


def test_apply_visual_intent_generalizes_buttocks_focus_for_any_npc() -> None:
    state = _state()
    npc = state.npcs.pop("victoria")
    npc.entity_id = "luna"
    npc.name = "Luna"
    state.npcs["luna"] = npc
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Osservo Luna mentre si allena",
        target_ids=["luna"],
    )
    vst = {
        "subjects": [{"entity_id": "luna", "pose": "dynamic stretch", "pose_tags": ["training"]}],
        "camera": {},
    }

    result = apply_visual_intent(
        vst,
        state,
        proposal,
        "guardo il suo culo mentre si allena sulla spiaggia",
    )

    assert result["visual_focus"]["subject_id"] == "luna"
    assert result["visual_focus"]["target_region"] == "buttocks"
    assert result["camera"]["shot_type"] == "medium_full_shot"
    assert result["camera"]["orientation"] == "rear_three_quarter"
    assert "buttocks clearly visible" in result["camera"]["framing_requirements"]


def test_body_focus_rules_are_npc_agnostic_for_resort_cast() -> None:
    for npc_id in ("victoria", "stella", "maria", "luna"):
        state = _state()
        original = state.npcs.pop("victoria")
        original.entity_id = npc_id
        original.name = npc_id.capitalize()
        state.npcs[npc_id] = original
        proposal = CheckProposal(
            check_type=CheckType.NO_CHECK,
            description=f"Osservo {npc_id}",
            target_ids=[npc_id],
        )
        vst = {
            "subjects": [{"entity_id": npc_id, "pose": "natural standing pose", "pose_tags": []}],
            "camera": {},
        }

        result = apply_visual_intent(vst, state, proposal, "guardo il suo culo")

        assert result["visual_focus"]["subject_id"] == npc_id
        assert result["visual_focus"]["target_region"] == "buttocks"
        assert result["camera"]["orientation"] == "rear_three_quarter"


def test_pose_variety_uses_worldpack_pose_library() -> None:
    state = _state()
    state.rendering_config["pose_library"] = {
        "default": [
            {"id": "custom_seated", "prompt": "custom seated pose", "tags": ["seated"]},
        ],
        "focus": {},
        "actions": {},
    }
    proposal = CheckProposal(check_type=CheckType.NO_CHECK, description="Parlo", target_ids=["victoria"])
    vst = {"subjects": [{"entity_id": "victoria", "pose": "natural standing pose", "pose_tags": []}]}

    result = apply_visual_intent(vst, state, proposal, "parlo con Victoria")

    assert result["subjects"][0]["pose"] == "custom seated pose"
    assert "seated" in result["subjects"][0]["pose_tags"]


def test_body_focus_pose_uses_worldpack_focus_library_for_any_npc() -> None:
    state = _state()
    npc = state.npcs.pop("victoria")
    npc.entity_id = "luna"
    npc.name = "Luna"
    state.npcs["luna"] = npc
    state.rendering_config["pose_library"] = {
        "default": [],
        "focus": {
            "buttocks": [
                {
                    "id": "training_rear",
                    "prompt": "deep forward training stretch with hips angled toward camera",
                    "tags": ["training", "forward stretch"],
                }
            ]
        },
        "actions": {},
    }
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Osservo Luna",
        target_ids=["luna"],
    )
    vst = {"subjects": [{"entity_id": "luna", "pose": "natural standing pose", "pose_tags": []}], "camera": {}}

    result = apply_visual_intent(vst, state, proposal, "guardo il suo culo mentre si allena")

    assert result["subjects"][0]["pose"] == "deep forward training stretch with hips angled toward camera"
    assert "forward stretch" in result["subjects"][0]["pose_tags"]


def test_shoe_removal_uses_worldpack_action_pose() -> None:
    state = _state()
    state.rendering_config["pose_library"] = {
        "default": [],
        "focus": {},
        "actions": {
            "shoe_removal": [
                {"id": "shoe_action", "prompt": "custom shoe removal pose", "tags": ["seated", "shoe removal"]}
            ]
        },
    }
    proposal = CheckProposal(check_type=CheckType.NO_CHECK, description="Parlo", target_ids=["victoria"])
    vst = {
        "subjects": [{"entity_id": "victoria", "pose": "standing", "pose_tags": []}],
        "camera": {},
        "action": {"description": "conversation", "interaction": "conversation"},
    }

    result = apply_visual_intent(vst, state, proposal, "mentre lei si toglie le scarpe")

    assert result["subjects"][0]["pose"] == "custom shoe removal pose"
    assert "shoe removal" in result["subjects"][0]["pose_tags"]
