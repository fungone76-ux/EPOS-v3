from pathlib import Path

from epos_v3.application.camera_library import select_focus_camera
from epos_v3.application.pose_library import select_pose
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


WORLD = Path(__file__).parents[2] / "worldpacks" / "resort_world"


def test_worldpack_loads_separate_visual_catalogs() -> None:
    state = WorldpackLoader().load(WORLD, session_id="catalogs").world

    for key in (
        "pose_library",
        "camera_library",
        "action_library",
        "outfit_library",
        "adult_intimacy_library",
    ):
        value = state.rendering_config.get(key)
        assert isinstance(value, dict), key
        assert value.get("world_id") == "resort_world"


def test_pose_selection_uses_focus_set_from_worldpack() -> None:
    state = WorldpackLoader().load(WORLD, session_id="pose-catalog").world

    selected = select_pose(
        state,
        entity_id="luna",
        category="focus",
        focus_region="buttocks",
    )

    assert selected is not None
    prompt, tags = selected
    assert prompt
    assert tags
    allowed = state.rendering_config["pose_library"]["focus_sets"]["buttocks"]
    pose_entries = state.rendering_config["pose_library"]["poses"]
    selected_ids = [pose_id for pose_id in allowed if any(tag in pose_entries[pose_id]["tags"] for tag in tags)]
    assert selected_ids


def test_camera_selection_uses_focus_set_and_framing_rules() -> None:
    state = WorldpackLoader().load(WORLD, session_id="camera-catalog").world

    selected = select_focus_camera(state, entity_id="luna", focus_region="buttocks")

    assert selected is not None
    assert selected["orientation"] in {"rear_three_quarter", "side"}
    assert "lower body clearly visible" in selected["framing_requirements"]
    assert "lower body cropped" in selected["negative_framing_requirements"]


def test_outfit_library_is_metadata_not_an_inventory_replacement() -> None:
    state = WorldpackLoader().load(WORLD, session_id="outfit-catalog").world
    library = state.rendering_config["outfit_library"]

    assert library["defaults"]["authoritative_source"] == "npc_wardrobes.yaml"
    assert library["rules"]["never_invent_item"] is True


def test_adult_intimacy_library_requires_consent_and_is_non_graphic() -> None:
    state = WorldpackLoader().load(WORLD, session_id="adult-catalog").world
    library = state.rendering_config["adult_intimacy_library"]

    assert library["defaults"]["adults_only"] is True
    assert library["defaults"]["consent_required"] is True
    assert library["rules"]["no_explicit_anatomical_action_tags"] is True
