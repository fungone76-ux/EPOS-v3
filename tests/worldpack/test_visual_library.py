from pathlib import Path

from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


WORLD = Path(__file__).parents[2] / "worldpacks" / "resort_world"


def test_resort_world_loads_pose_library_into_runtime_config() -> None:
    state = WorldpackLoader().load(WORLD, session_id="pose-library").world

    library = state.rendering_config.get("pose_library")
    assert isinstance(library, dict)
    assert library.get("library_type") == "pose"
    poses = library.get("poses")
    assert isinstance(poses, dict)
    assert "seated_legs_crossed" in poses
    focus = library.get("focus_sets")
    assert isinstance(focus, dict)
    assert "legs" in focus
    assert "buttocks" in focus
    actions = library.get("action_compatibility")
    assert isinstance(actions, dict)
    assert "shoe_removal" in actions
