from pathlib import Path

import pytest

from epos_v3.domain.world import TimeOfDay
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


ROOT = Path(__file__).parents[2] / "worldpacks" / "resort_world"


def test_load_real_worldpack_and_build_initial_state() -> None:
    loaded = WorldpackLoader().load(ROOT)

    assert loaded.world.worldpack_id == "resort_world"
    assert loaded.world.session_id == "pending"
    assert loaded.world.day == 1
    assert loaded.world.time_of_day is TimeOfDay.MORNING
    assert loaded.world.player.location_id == "loc_lobby"
    assert set(loaded.world.npcs) == {"victoria", "stella", "maria", "luna"}
    assert len(loaded.world.locations) == 9
    assert loaded.world.npcs["victoria"].outfit[0].name == "ivory bodycon blazer mini dress"


def test_schedule_and_wardrobe_follow_day_and_phase() -> None:
    loaded = WorldpackLoader().load(ROOT, session_id="azure-001")

    assert loaded.world.session_id == "azure-001"
    loaded.apply_clock(day=3, phase="sera")

    assert loaded.world.npcs["victoria"].location_id == "loc_victoria_office"
    assert loaded.world.npcs["victoria"].outfit[0].name == "plum bodycon office dress"
    assert loaded.world.npcs["luna"].location_id == "loc_wild_beach"
    assert loaded.world.npcs["luna"].outfit[0].name == "dark blue sheer beach dress"
    assert "victoria" in loaded.world.locations["loc_victoria_office"].npcs_present
    assert "luna" in loaded.world.locations["loc_wild_beach"].npcs_present


def test_invalid_reference_is_rejected(tmp_path: Path) -> None:
    for source in ROOT.iterdir():
        (tmp_path / source.name).write_bytes(source.read_bytes())
    schedule = tmp_path / "npc_schedules.yaml"
    text = schedule.read_text(encoding="utf-8")
    schedule.write_text(text.replace("loc_lobby", "loc_missing", 1), encoding="utf-8")

    with pytest.raises(ValueError, match="loc_missing"):
        WorldpackLoader().load(tmp_path)


def test_worldpack_with_different_identity_is_supported(tmp_path: Path) -> None:
    for source in ROOT.iterdir():
        (tmp_path / source.name).write_bytes(source.read_bytes())
    for filename in tmp_path.iterdir():
        text = filename.read_text(encoding="utf-8")
        text = text.replace("resort_world", "different_world")
        filename.write_text(text, encoding="utf-8")

    loaded = WorldpackLoader().load(tmp_path)

    assert loaded.world.worldpack_id == "different_world"
    assert loaded.world.npcs["victoria"].name == "Victoria Hale"


def test_cli_can_load_a_real_worldpack() -> None:
    from epos_v3.presentation.cli import build_worldpack_world

    state = build_worldpack_world(ROOT, session_id="cli-azure")

    assert state.session_id == "cli-azure"
    assert state.worldpack_id == "resort_world"
    assert state.player.location_id == "loc_lobby"


def test_resort_world_exposes_comfy_workflow_configuration() -> None:
    from pathlib import Path
    from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

    root = Path(__file__).resolve().parents[2] / "worldpacks" / "resort_world"
    loaded = WorldpackLoader().load(root, session_id="render-config")

    assert loaded.world.rendering_config["workflow_file"] == "comfy_workflow_image.json"
    assert (root / str(loaded.world.rendering_config["workflow_file"])).is_file()


def test_worldpack_rejects_unregistered_lora_alias(tmp_path: Path) -> None:
    import shutil
    import yaml

    root = Path(__file__).resolve().parents[2] / "worldpacks" / "resort_world"
    target = tmp_path / "broken_visual"
    shutil.copytree(root, target)
    visual_path = target / "visual.yaml"
    visual = yaml.safe_load(visual_path.read_text(encoding="utf-8"))
    visual["characters"][0]["base_prompt"] = "portrait <lora:missing_alias:0.5>"
    visual_path.write_text(yaml.safe_dump(visual, sort_keys=False), encoding="utf-8")

    try:
        WorldpackLoader().load(target)
    except ValueError as exc:
        assert "missing_alias" in str(exc)
        assert "LoRA" in str(exc)
    else:
        raise AssertionError("unregistered LoRA aliases must fail Worldpack loading")
