import json
from pathlib import Path

from epos_v3.infrastructure.rendering.comfyui import ComfyUIAdapter


def test_adapter_resolves_worldpack_workflow_and_binds_contract(tmp_path: Path) -> None:
    world_dir = tmp_path / "worldpacks" / "resort_world"
    world_dir.mkdir(parents=True)
    workflow_path = world_dir / "image.json"
    workflow_path.write_text(json.dumps({
        "1": {"inputs": {"ckpt_name": "model.safetensors"}, "class_type": "CheckpointLoaderSimple"},
        "2": {"inputs": {"text": "RUNTIME_POSITIVE_PROMPT"}, "class_type": "CLIPTextEncode", "_meta": {"title": "Prompt"}},
        "3": {"inputs": {"text": "old negative"}, "class_type": "CLIPTextEncode", "_meta": {"title": "Negative Prompt"}},
        "7": {"inputs": {"width": 896, "height": 1152}, "class_type": "EmptyLatentImage"},
    }), encoding="utf-8")

    adapter = ComfyUIAdapter(worldpack_root=tmp_path / "worldpacks", image_dir=tmp_path / "images")
    workflow = adapter.build_workflow({
        "worldpack_id": "resort_world",
        "workflow_file": "image.json",
        "prompt": "runtime scene",
        "negative_prompt": "runtime negative",
        "width": 1024,
        "height": 1344,
    })

    assert workflow["2"]["inputs"]["text"] == "runtime scene"
    assert workflow["3"]["inputs"]["text"] == "runtime negative"
    assert workflow["7"]["inputs"]["width"] == 1024
    assert workflow["7"]["inputs"]["height"] == 1344


def test_adapter_rejects_workflow_path_escape(tmp_path: Path) -> None:
    adapter = ComfyUIAdapter(worldpack_root=tmp_path / "worldpacks", image_dir=tmp_path / "images")

    try:
        adapter.build_workflow({
            "worldpack_id": "resort_world",
            "workflow_file": "../../outside.json",
            "prompt": "scene",
            "negative_prompt": "negative",
        })
    except ValueError as exc:
        assert "workflow" in str(exc).lower()
    else:
        raise AssertionError("path traversal must be rejected")


def test_comfy_adapter_defaults_to_120s_and_three_attempts(tmp_path: Path) -> None:
    adapter = ComfyUIAdapter(worldpack_root=tmp_path / "worldpacks", image_dir=tmp_path / "images")
    assert adapter.timeout == 120
    assert adapter.max_attempts == 3


def test_comfy_adapter_retries_transient_render_failures(tmp_path: Path) -> None:
    import asyncio

    adapter = ComfyUIAdapter(worldpack_root=tmp_path / "worldpacks", image_dir=tmp_path / "images", retry_delay=0.0)
    attempts = 0

    async def flaky(_: dict[str, object]) -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("temporary")
        return "/tmp/final.png"

    adapter._render_once = flaky  # type: ignore[method-assign]
    result = asyncio.run(adapter.render({"prompt": "x", "negative_prompt": "y"}))

    assert result == "/tmp/final.png"
    assert attempts == 3
