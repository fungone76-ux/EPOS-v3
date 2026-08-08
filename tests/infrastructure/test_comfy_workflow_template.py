import json
from pathlib import Path

from epos_v3.infrastructure.rendering.workflow_template import ComfyWorkflowTemplate


def _write_template(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "1": {"inputs": {"ckpt_name": "model.safetensors"}, "class_type": "CheckpointLoaderSimple", "_meta": {"title": "Load Checkpoint"}},
                "2": {"inputs": {"text": "RUNTIME_POSITIVE_PROMPT", "clip": ["25", 1]}, "class_type": "CLIPTextEncode", "_meta": {"title": "CLIP Text Encode (Prompt)"}},
                "3": {"inputs": {"text": "base negative", "clip": ["25", 1]}, "class_type": "CLIPTextEncode", "_meta": {"title": "CLIP Text Encode (Negative Prompt)"}},
                "4": {"inputs": {"noise_seed": 11, "cfg": 7, "model": ["25", 0]}, "class_type": "SamplerCustom", "_meta": {"title": "SamplerCustom"}},
                "7": {"inputs": {"width": 896, "height": 1152, "batch_size": 1}, "class_type": "EmptyLatentImage", "_meta": {"title": "Empty Latent Image"}},
            }
        ),
        encoding="utf-8",
    )


def test_workflow_template_injects_runtime_prompt_negative_and_dimensions(tmp_path: Path) -> None:
    template_path = tmp_path / "workflow.json"
    _write_template(template_path)
    binder = ComfyWorkflowTemplate(template_path)

    workflow = binder.build(
        {
            "prompt": "cinematic beach, victoria",
            "negative_prompt": "bad anatomy, watermark",
            "width": 1024,
            "height": 1344,
        }
    )

    assert workflow["2"]["inputs"]["text"] == "cinematic beach, victoria"
    assert workflow["3"]["inputs"]["text"] == "bad anatomy, watermark"
    assert workflow["7"]["inputs"]["width"] == 1024
    assert workflow["7"]["inputs"]["height"] == 1344
    assert workflow["1"]["inputs"]["ckpt_name"] == "model.safetensors"
    assert workflow["4"]["inputs"]["noise_seed"] == 11


def test_workflow_template_can_override_seed_cfg_and_checkpoint(tmp_path: Path) -> None:
    template_path = tmp_path / "workflow.json"
    _write_template(template_path)
    binder = ComfyWorkflowTemplate(template_path)

    workflow = binder.build(
        {
            "prompt": "scene",
            "negative_prompt": "negative",
            "seed": 99,
            "cfg": 5.5,
            "checkpoint": "other.safetensors",
        }
    )

    assert workflow["4"]["inputs"]["noise_seed"] == 99
    assert workflow["4"]["inputs"]["cfg"] == 5.5
    assert workflow["1"]["inputs"]["ckpt_name"] == "other.safetensors"


def test_workflow_template_does_not_mutate_source(tmp_path: Path) -> None:
    template_path = tmp_path / "workflow.json"
    _write_template(template_path)
    binder = ComfyWorkflowTemplate(template_path)

    first = binder.build({"prompt": "one", "negative_prompt": "n"})
    second = binder.build({"prompt": "two", "negative_prompt": "n"})

    assert first["2"]["inputs"]["text"] == "one"
    assert second["2"]["inputs"]["text"] == "two"


def _write_lora_template(path: Path) -> None:
    workflow = {
        "2": {"inputs": {"text": "RUNTIME_POSITIVE_PROMPT"}, "class_type": "CLIPTextEncode", "_meta": {"title": "Prompt"}},
        "3": {"inputs": {"text": "base negative"}, "class_type": "CLIPTextEncode", "_meta": {"title": "Negative Prompt"}},
    }
    previous = "1"
    workflow["1"] = {"inputs": {"ckpt_name": "model.safetensors"}, "class_type": "CheckpointLoaderSimple"}
    for node_id in range(20, 26):
        workflow[str(node_id)] = {
            "inputs": {
                "lora_name": "placeholder.safetensors",
                "strength_model": 0.0,
                "strength_clip": 0.0,
                "model": [previous, 0],
                "clip": [previous, 1],
            },
            "class_type": "LoraLoader",
        }
        previous = str(node_id)
    path.write_text(json.dumps(workflow), encoding="utf-8")


def test_workflow_template_binds_dynamic_lora_slots(tmp_path: Path) -> None:
    template_path = tmp_path / "workflow.json"
    _write_lora_template(template_path)
    binder = ComfyWorkflowTemplate(template_path)

    workflow = binder.build({
        "prompt": "scene",
        "negative_prompt": "negative",
        "loras": [
            {"name": "hero.safetensors", "weight": 0.75},
            {"name": "expression.safetensors", "strength_model": 0.4, "strength_clip": 0.2},
        ],
    })

    assert workflow["20"]["inputs"]["lora_name"] == "hero.safetensors"
    assert workflow["20"]["inputs"]["strength_model"] == 0.75
    assert workflow["20"]["inputs"]["strength_clip"] == 0.75
    assert workflow["21"]["inputs"]["lora_name"] == "expression.safetensors"
    assert workflow["21"]["inputs"]["strength_model"] == 0.4
    assert workflow["21"]["inputs"]["strength_clip"] == 0.2
    for node_id in range(22, 26):
        assert workflow[str(node_id)]["inputs"]["strength_model"] == 0.0
        assert workflow[str(node_id)]["inputs"]["strength_clip"] == 0.0


def test_workflow_template_rejects_more_loras_than_available_slots(tmp_path: Path) -> None:
    template_path = tmp_path / "workflow.json"
    _write_lora_template(template_path)
    binder = ComfyWorkflowTemplate(template_path)

    try:
        binder.build({
            "prompt": "scene",
            "negative_prompt": "negative",
            "loras": [{"name": f"lora_{index}.safetensors", "weight": 0.5} for index in range(7)],
        })
    except ValueError as exc:
        assert "lora" in str(exc).lower()
        assert "6" in str(exc)
    else:
        raise AssertionError("too many LoRAs must be rejected")
