"""Deterministic binding of runtime render values into a ComfyUI workflow template."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]


class ComfyWorkflowTemplate:
    """Load a ComfyUI API workflow and inject only approved runtime fields."""

    POSITIVE_PLACEHOLDER = "RUNTIME_POSITIVE_PROMPT"

    def __init__(self, path: str | Path) -> None:
        """Load and validate a workflow template from disk.

        Args:
            path: Path to a ComfyUI API-format workflow JSON file.

        Raises:
            ValueError: If the workflow is not a JSON object or lacks required nodes.
        """
        self.path = Path(path)
        raw: JsonValue = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("ComfyUI workflow must be a JSON object")
        self._template = cast(JsonObject, raw)
        self._validate_required_nodes(self._template)

    def build(self, contract: JsonObject) -> JsonObject:
        """Return a deep-copied workflow populated with approved runtime values.

        Args:
            contract: Renderer contract containing prompt fields and optional overrides.

        Returns:
            A standalone ComfyUI workflow dictionary ready for `/prompt`.
        """
        workflow = copy.deepcopy(self._template)
        positive = _require_string(contract, "prompt")
        negative = _require_string(contract, "negative_prompt")

        positive_node = self._find_positive_node(workflow)
        negative_node = self._find_negative_node(workflow, positive_node)
        _inputs(positive_node)["text"] = positive
        _inputs(negative_node)["text"] = negative

        latent = self._find_node(workflow, "EmptyLatentImage")
        if latent is not None:
            latent_inputs = _inputs(latent)
            if "width" in contract:
                latent_inputs["width"] = _require_int(contract, "width")
            if "height" in contract:
                latent_inputs["height"] = _require_int(contract, "height")

        sampler = self._find_node(workflow, "SamplerCustom")
        if sampler is not None:
            sampler_inputs = _inputs(sampler)
            if "seed" in contract:
                sampler_inputs["noise_seed"] = _require_int(contract, "seed")
            if "cfg" in contract:
                sampler_inputs["cfg"] = _require_number(contract, "cfg")

        checkpoint = self._find_node(workflow, "CheckpointLoaderSimple")
        if checkpoint is not None and "checkpoint" in contract:
            _inputs(checkpoint)["ckpt_name"] = _require_string(contract, "checkpoint")

        self._bind_loras(workflow, contract)
        return workflow

    def _validate_required_nodes(self, workflow: JsonObject) -> None:
        """Validate the minimum runtime contract expected by EPOS."""
        positive = self._find_positive_node(workflow)
        if positive is None:
            raise ValueError(f"workflow missing positive prompt placeholder {self.POSITIVE_PLACEHOLDER!r}")
        if self._find_negative_node(workflow, positive) is None:
            raise ValueError("workflow missing negative CLIPTextEncode node")

    def _find_positive_node(self, workflow: JsonObject) -> JsonObject | None:
        """Execute the find positive node operation."""
        for node in _nodes(workflow):
            if node.get("class_type") != "CLIPTextEncode":
                continue
            if _inputs(node).get("text") == self.POSITIVE_PLACEHOLDER:
                return node
        return None

    def _find_negative_node(self, workflow: JsonObject, positive: JsonObject | None) -> JsonObject | None:
        """Execute the find negative node operation."""
        candidates = [node for node in _nodes(workflow) if node.get("class_type") == "CLIPTextEncode" and node is not positive]
        for node in candidates:
            meta = node.get("_meta")
            if isinstance(meta, dict) and "negative" in str(meta.get("title", "")).lower():
                return node
        return candidates[0] if candidates else None

    def _bind_loras(self, workflow: JsonObject, contract: JsonObject) -> None:
        """Bind requested LoRAs to workflow slots in deterministic node order."""
        requested = contract.get("loras", [])
        if not isinstance(requested, list):
            raise ValueError("render contract 'loras' must be a list")
        slots = [node for node in _nodes(workflow) if node.get("class_type") == "LoraLoader"]
        if len(requested) > len(slots):
            raise ValueError(f"render contract requests {len(requested)} LoRAs but workflow has only {len(slots)} slots")

        for slot in slots:
            inputs = _inputs(slot)
            inputs["strength_model"] = 0.0
            inputs["strength_clip"] = 0.0

        for index, raw in enumerate(requested):
            if not isinstance(raw, dict):
                raise ValueError("each LoRA entry must be an object")
            spec = cast(JsonObject, raw)
            name = _require_string(spec, "name")
            default_weight = spec.get("weight", 1.0)
            if isinstance(default_weight, bool) or not isinstance(default_weight, (int, float)):
                raise ValueError("LoRA weight must be numeric")
            model_strength = spec.get("strength_model", default_weight)
            clip_strength = spec.get("strength_clip", default_weight)
            if isinstance(model_strength, bool) or not isinstance(model_strength, (int, float)):
                raise ValueError("LoRA strength_model must be numeric")
            if isinstance(clip_strength, bool) or not isinstance(clip_strength, (int, float)):
                raise ValueError("LoRA strength_clip must be numeric")
            inputs = _inputs(slots[index])
            inputs["lora_name"] = name
            inputs["strength_model"] = model_strength
            inputs["strength_clip"] = clip_strength

    @staticmethod
    def _find_node(workflow: JsonObject, class_type: str) -> JsonObject | None:
        """Execute the find node operation."""
        return next((node for node in _nodes(workflow) if node.get("class_type") == class_type), None)


def _nodes(workflow: JsonObject) -> list[JsonObject]:
    """Execute the nodes operation."""
    result: list[JsonObject] = []
    for value in workflow.values():
        if isinstance(value, dict):
            result.append(cast(JsonObject, value))
    return result


def _inputs(node: JsonObject) -> JsonObject:
    """Execute the inputs operation."""
    value = node.get("inputs")
    if not isinstance(value, dict):
        raise ValueError("ComfyUI node is missing an inputs object")
    return cast(JsonObject, value)


def _require_string(contract: JsonObject, key: str) -> str:
    """Execute the require string operation."""
    value = contract.get(key)
    if not isinstance(value, str):
        raise ValueError(f"render contract {key!r} must be a string")
    return value


def _require_int(contract: JsonObject, key: str) -> int:
    """Execute the require int operation."""
    value = contract.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"render contract {key!r} must be an integer")
    return value


def _require_number(contract: JsonObject, key: str) -> int | float:
    """Execute the require number operation."""
    value = contract.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"render contract {key!r} must be numeric")
    return value
