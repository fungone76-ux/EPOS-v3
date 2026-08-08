from epos_v3.application.visual_intent import apply_visual_intent
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.infrastructure.visual.world_compiler import WorldVisualCompiler


def test_bare_feet_intent_removes_authoritative_shoes_from_frame(sample_world) -> None:
    npc = sample_world.npcs["npc"]
    from epos_v3.domain.outfit import OutfitItem

    npc.outfit = [
        OutfitItem(slot="visual", item_id="dress", name="black dress", coverage=1.0, layer=0),
        OutfitItem(slot="visual", item_id="heels", name="nude stiletto pumps", coverage=1.0, layer=1),
    ]
    vst = {
        "style": {"art_style": "cinematic", "color_palette": "warm", "mood": "quiet", "rendering": "detailed", "lora": [], "model": "default"},
        "location": {"location_id": "beach", "time_of_day": "morning", "lighting": "sunlight", "environment_tags": []},
        "subjects": [{"entity_id": "npc", "gender": "female", "pose": "standing", "pose_tags": [], "expression": "", "gaze": "", "outfit_visible": [], "body_state": "clothed", "skin_visible": []}],
        "action": {"description": "conversation", "interaction": "conversation"},
        "camera": {"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "depth_of_field": "deep", "background_blur": False},
        "lighting": {"primary": "soft", "rim_light": ""},
    }
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Parlo con lei",
        target_ids=["npc"],
    )

    focused = apply_visual_intent(vst, sample_world, proposal, "osservo i suoi piedi nudi")
    result = WorldVisualCompiler().compile(focused, sample_world)

    assert "nude stiletto pumps" not in result["prompt"]
    assert "bare feet" in result["prompt"]
    assert "focus on feet" in result["prompt"]
