from epos_v3.infrastructure.visual.world_compiler import WorldVisualCompiler


def test_world_visual_compiler_uses_authoritative_character_sheet(sample_world):
    npc = sample_world.npcs["npc"]
    npc.base_prompt = "canonical silver hair"
    npc.role_prompt = "canonical guide"
    npc.negative_prompt = "wrong face"
    vst = {
        "style": {
            "art_style": "cinematic",
            "color_palette": "warm",
            "mood": "quiet",
            "rendering": "detailed",
            "lora": [],
            "model": "default",
        },
        "location": {
            "location_id": "beach",
            "time_of_day": "morning",
            "lighting": "sunlight",
            "environment_tags": [],
        },
        "subjects": [
            {
                "entity_id": "npc",
                "gender": "female",
                "pose_tags": ["standing"],
                "expression": "smile",
                "gaze": "looking_at_viewer",
                "outfit_visible": [],
                "body_state": "clothed",
                "skin_visible": [],
            }
        ],
        "action": {"description": "talking", "interaction": "none"},
        "camera": {
            "shot_type": "medium_shot",
            "angle": "eye_level",
            "orientation": "front",
            "depth_of_field": "shallow",
            "background_blur": True,
        },
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "canonical silver hair" in result["prompt"]
    assert "canonical guide" in result["prompt"]
    assert "wrong face" in result["negative_prompt"]
    assert result["worldpack_id"] == sample_world.worldpack_id


def test_world_visual_compiler_forwards_worldpack_rendering_config(sample_world):
    sample_world.rendering_config = {"workflow_file": "comfy_workflow_image.json"}
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [],
        "action": {"description": "empty beach", "interaction": "none"},
        "camera": {"shot_type": "wide_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert result["workflow_file"] == "comfy_workflow_image.json"


def test_world_visual_compiler_resolves_character_loras_from_registry(sample_world):
    npc = sample_world.npcs["npc"]
    npc.base_prompt = "portrait <lora:HeroAlias:0.6>"
    npc.character_lora = [{"prompt": "<lora:ExpressionAlias:0.4>"}]
    sample_world.rendering_config = {
        "workflow_file": "comfy_workflow_image.json",
        "lora_registry": {
            "HeroAlias": "hero_exact.safetensors",
            "ExpressionAlias": "expression_exact.safetensors",
        },
    }
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "standing", "interaction": "none"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert result["loras"] == [
        {"name": "hero_exact.safetensors", "weight": 0.6},
        {"name": "expression_exact.safetensors", "weight": 0.4},
    ]
    assert "<lora:" not in result["prompt"]


def test_world_visual_compiler_rejects_unknown_lora_alias(sample_world):
    npc = sample_world.npcs["npc"]
    npc.base_prompt = "portrait <lora:UnknownAlias:0.5>"
    sample_world.rendering_config = {"lora_registry": {}}
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "standing", "interaction": "none"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    try:
        WorldVisualCompiler().compile(vst, sample_world)
    except ValueError as exc:
        assert "UnknownAlias" in str(exc)
    else:
        raise AssertionError("unknown LoRA aliases must be rejected")


def test_resort_world_four_npcs_fill_all_six_real_workflow_lora_slots() -> None:
    from pathlib import Path

    from epos_v3.infrastructure.rendering.workflow_template import ComfyWorkflowTemplate
    from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

    world_dir = Path(__file__).resolve().parents[2] / "worldpacks" / "resort_world"
    state = WorldpackLoader().load(world_dir, session_id="visual-six-lora").world
    for npc_id in ("victoria", "stella", "maria", "luna"):
        state.npcs[npc_id].location_id = state.player.location_id
        state.npcs[npc_id].is_present = True
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "social", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": state.player.location_id, "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [
            {"entity_id": npc_id, "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}
            for npc_id in ("victoria", "stella", "maria", "luna")
        ],
        "action": {"description": "group scene", "interaction": "conversation"},
        "camera": {"shot_type": "wide_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    contract = WorldVisualCompiler().compile(vst, state)
    assert [item["name"] for item in contract["loras"]] == [
        "Expressive_H-000001.safetensors",
        "FantasyWorldPonyV2.safetensors",
        "Zatanna_-_DC_Animated_Universe.safetensors",
        "alice_mitchell_milf_catchers_lora.safetensors",
        "stsSmith-10e.safetensors",
        "stsDebbie-10e.safetensors",
    ]

    workflow = ComfyWorkflowTemplate(world_dir / "comfy_workflow_image.json").build(contract)
    for offset, expected in enumerate(contract["loras"], start=20):
        assert workflow[str(offset)]["inputs"]["lora_name"] == expected["name"]
        assert workflow[str(offset)]["inputs"]["strength_model"] == expected["weight"]
        assert workflow[str(offset)]["inputs"]["strength_clip"] == expected["weight"]


def test_world_visual_compiler_overrides_llm_outfit_with_authoritative_state(sample_world):
    npc = sample_world.npcs["npc"]
    from epos_v3.domain.outfit import OutfitItem
    npc.outfit = [OutfitItem(slot="visual", item_id="canonical", name="canonical blue coat", coverage=1.0, layer=0)]
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [{"item": "invented red dress", "coverage": 1.0, "state": "worn", "material": "", "color": "red"}], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "standing", "interaction": "none"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "canonical blue coat" in result["prompt"]
    assert "invented red dress" not in result["prompt"]


def test_world_visual_compiler_enforces_worldpack_visual_style(sample_world):
    sample_world.rendering_config = {"visual_style_en": "authoritative noir photography"}
    vst = {
        "style": {"art_style": "invented fantasy watercolor", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [],
        "action": {"description": "empty scene", "interaction": "none"},
        "camera": {"shot_type": "wide_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "authoritative noir photography" in result["prompt"]
    assert "invented fantasy watercolor" not in result["prompt"]


def test_world_visual_compiler_rejects_npc_outside_player_location(sample_world):
    sample_world.npcs["npc"].location_id = "office"
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "impossible cutaway", "interaction": "none"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    try:
        WorldVisualCompiler().compile(vst, sample_world)
    except ValueError as exc:
        assert "not present at player location" in str(exc)
    else:
        raise AssertionError("NPCs outside the player's location must not appear in the VST")


def test_world_visual_compiler_canonicalizes_scene_location_to_player(sample_world):
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "office", "time_of_day": "morning", "lighting": "artificial", "environment_tags": []},
        "subjects": [],
        "action": {"description": "local scene", "interaction": "none"},
        "camera": {"shot_type": "wide_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert result["vst"]["location"]["location_id"] == sample_world.player.location_id


def test_world_visual_compiler_includes_worldpack_negative_prompt(sample_world):
    sample_world.rendering_config = {"negative_extra_en": "forbidden_worldpack_artifact"}
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [],
        "action": {"description": "empty beach", "interaction": "none"},
        "camera": {"shot_type": "wide_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "forbidden_worldpack_artifact" in result["negative_prompt"]


def test_resort_world_loader_preserves_negative_extra_prompt() -> None:
    from pathlib import Path
    from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

    world_dir = Path(__file__).resolve().parents[2] / "worldpacks" / "resort_world"
    state = WorldpackLoader().load(world_dir, session_id="negative-extra").world

    assert "underage" in str(state.rendering_config.get("negative_extra_en", ""))


def test_visual_focus_compiles_to_deterministic_camera_requirements(sample_world):
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": ["seated", "legs crossed"], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "sits and crosses her legs", "interaction": "none"},
        "visual_focus": {"subject_id": "npc", "target_region": "feet", "priority": "primary", "gaze_source": "player"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "feet clearly visible" in result["prompt"]
    assert "both feet fully in frame" in result["prompt"]
    assert "visual focus on feet" in result["prompt"]
    assert "cropped feet" in result["negative_prompt"]


def test_visual_focus_rejects_subject_not_in_scene(sample_world):
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "standing", "interaction": "none"},
        "visual_focus": {"subject_id": "ghost", "target_region": "feet", "priority": "primary", "gaze_source": "player"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    try:
        WorldVisualCompiler().compile(vst, sample_world)
    except ValueError as exc:
        assert "visual focus subject" in str(exc)
    else:
        raise AssertionError("focus subject must be visible in the scene")


def test_prompt_compiler_omits_player_subject_but_keeps_npc(sample_world):
    from epos_v3.domain.entities import Player

    sample_world.player = Player(
        entity_id="player",
        name="Player",
        outfit=[],
        stats={},
        inventory=[],
        location_id="beach",
        conditions=[],
        knowledge=[],
    )
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [
            {"entity_id": "player", "gender": "male", "pose_tags": ["standing"], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []},
            {"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "smile", "gaze": "at viewer", "outfit_visible": [], "body_state": "clothed", "skin_visible": []},
        ],
        "action": {"description": "Player greets the NPC with a smile.", "interaction": "Player speaks to NPC"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "shallow", "background_blur": True},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "Player greets" not in result["prompt"]
    assert "1boy" not in result["prompt"]
    assert "greeting" in result["prompt"]


def test_world_visual_compiler_deduplicates_negative_prompt(sample_world):
    sample_world.npcs["npc"].negative_prompt = "bad anatomy, duplicate person"
    sample_world.rendering_config = {
        "negative_extra_en": "bad anatomy, duplicate person, underage"
    }
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "standing", "interaction": "none"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    tags = [part.strip() for part in result["negative_prompt"].split(",")]
    assert tags.count("bad anatomy") == 1
    assert tags.count("duplicate person") == 1


def test_world_visual_compiler_includes_pose_and_region_focus(sample_world):
    npc = sample_world.npcs["npc"]
    npc.base_prompt = "mature woman"
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose": "seated with legs crossed", "pose_tags": ["seated", "crossed legs"], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "visual_focus": {"subject_id": "npc", "target_region": "legs", "priority": "primary", "gaze_source": "viewer"},
        "action": {"description": "conversation", "interaction": "none"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "seated with legs crossed" in result["prompt"]
    assert "focus on legs" in result["prompt"]


def test_world_visual_compiler_deduplicates_positive_prompt(sample_world) -> None:
    sample_world.npcs["npc"].base_prompt = "realistic, realistic, mature woman"
    vst = {
        "style": {"art_style": "realistic", "color_palette": "warm", "mood": "none", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "standing", "interaction": "none"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": "none"},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)
    tags = [item.strip() for item in result["prompt"].split(",")]

    assert tags.count("realistic") == 1
    assert "none" not in tags



def test_world_visual_compiler_applies_default_loras_to_any_scene(sample_world):
    sample_world.rendering_config = {
        "lora_registry": {
            "Expressive_H": "Expressive_H-000001.safetensors",
            "FantasyWorldPonyV2": "FantasyWorldPonyV2.safetensors",
            "CharacterAlias": "character_exact.safetensors",
        },
        "default_loras": [
            {"name": "Expressive_H", "weight": 0.4},
            {"name": "FantasyWorldPonyV2", "weight": 0.3},
        ],
    }
    npc = sample_world.npcs["npc"]
    npc.base_prompt = "portrait <lora:CharacterAlias:0.7>"
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "smiling", "gaze": "direct", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "speaks warmly and smiles", "interaction": "conversation"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert result["loras"] == [
        {"name": "Expressive_H-000001.safetensors", "weight": 0.4},
        {"name": "FantasyWorldPonyV2.safetensors", "weight": 0.3},
        {"name": "character_exact.safetensors", "weight": 0.7},
    ]
    assert "smiling" not in result["prompt"]
    assert "direct" not in result["prompt"]
    assert "smile" not in result["prompt"]


def test_world_visual_compiler_expands_worldpack_action_id(sample_world):
    sample_world.rendering_config["action_library"] = {
        "library_type": "action",
        "world_id": sample_world.worldpack_id,
        "actions": {
            "stretching": {
                "tags": ["stretching", "arms raised"],
                "aliases": ["fa stretching"],
            }
        },
    }
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"type": "action", "action_id": "stretching", "description": "generic prose ignored", "interaction": "none", "intensity": "neutral", "narrative_moment": ""},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }

    result = WorldVisualCompiler().compile(vst, sample_world)

    assert "stretching" in result["prompt"]
    assert "arms raised" in result["prompt"]
    assert "generic prose ignored" not in result["prompt"]
