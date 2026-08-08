"""Runtime adapter from authoritative WorldState + VST to render contract."""

from __future__ import annotations

import copy
import re

from epos_v3.application.action_library import resolve_action_tags
from epos_v3.application.camera_library import select_focus_camera
from epos_v3.application.visual_canonicalizer import canonicalize_vst

from epos_v3.domain.world import WorldState
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.types import JSONObject

from .prompt_compiler import SemanticPromptCompiler
from .prompt_sanitizer import dedupe_prompt_tags
from .vst_models import VisualSemanticTable

_LORA_TAG_RE = re.compile(r"<lora:([^:>]+):([0-9]*\.?[0-9]+)>")


class WorldVisualCompiler:
    """Compile a VST using canonical character sheets from the current world state."""

    def __init__(self, compiler: SemanticPromptCompiler | None = None) -> None:
        """Create the adapter around the deterministic semantic prompt compiler."""
        self._compiler = compiler or SemanticPromptCompiler()

    def compile(self, vst: JSONObject, state: WorldState) -> JSONObject:
        """Compile a renderer contract without trusting LLM identity or outfit data."""
        canonical_vst = canonicalize_vst(copy.deepcopy(vst), state)
        _validate_player_scene_scope(canonical_vst, state)
        visual_keys = set(VisualSemanticTable.model_fields)
        visual_vst = VisualSemanticTable.model_validate(
            {key: value for key, value in canonical_vst.items() if key in visual_keys}
        ).model_dump(mode="python")
        _apply_visual_focus(visual_vst, state)
        _apply_action_library(visual_vst, state)
        _apply_authoritative_outfits(visual_vst, state)
        _apply_transient_visual_state(visual_vst)
        visual_style = state.rendering_config.get("visual_style_en")
        if isinstance(visual_style, str) and visual_style:
            style = visual_vst.get("style")
            if isinstance(style, dict):
                style["art_style"] = visual_style
        visible_ids = {
            str(subject.get("entity_id"))
            for subject in visual_vst.get("subjects", [])
            if isinstance(subject, dict) and subject.get("entity_id")
        }
        registry = _lora_registry(state)
        loras: list[dict[str, object]] = []
        seen: set[tuple[str, float]] = set()
        for alias, weight in _default_loras(state):
            _append_resolved_lora(loras, seen, registry, alias, weight)
        character_sheets: dict[str, JSONObject] = {}

        for npc in state.npcs.values():
            base_prompt, base_loras = _strip_lora_tags(npc.base_prompt)
            character_lora_texts = [
                str(item.get("prompt", ""))
                for item in npc.character_lora
                if isinstance(item, dict)
            ]
            char_loras: list[tuple[str, float]] = []
            for text in character_lora_texts:
                _, extracted = _strip_lora_tags(text)
                char_loras.extend(extracted)
            if npc.entity_id in visible_ids:
                for alias, weight in [*base_loras, *char_loras]:
                    _append_resolved_lora(loras, seen, registry, alias, weight)
            character_sheets[npc.entity_id] = {
                "base_prompt": base_prompt,
                "role_prompt": npc.role_prompt,
                "negative_prompt": npc.negative_prompt,
                "character_lora": [],
            }

        result = self._compiler.compile(visual_vst, character_sheets)
        negative_extra = state.rendering_config.get("negative_extra_en")
        if isinstance(negative_extra, str) and negative_extra.strip():
            existing_negative = str(result.get("negative_prompt", "")).strip()
            result["negative_prompt"] = ", ".join(
                part for part in (existing_negative, negative_extra.strip()) if part
            )
        prompt, style_loras = _strip_lora_tags(str(result["prompt"]))
        result["prompt"] = dedupe_prompt_tags(prompt)
        for alias, weight in style_loras:
            _append_resolved_lora(loras, seen, registry, alias, weight)
        for raw in visual_vst.get("style", {}).get("lora", []):
            if not isinstance(raw, dict):
                raise ValueError("VST style LoRA entries must be objects")
            alias = raw.get("name")
            weight = raw.get("weight", 1.0)
            if not isinstance(alias, str) or not alias:
                raise ValueError("VST style LoRA name must be a non-empty string")
            if isinstance(weight, bool) or not isinstance(weight, (int, float)):
                raise ValueError("VST style LoRA weight must be numeric")
            _append_resolved_lora(loras, seen, registry, alias, float(weight))

        result["negative_prompt"] = dedupe_prompt_tags(
            str(result.get("negative_prompt", ""))
        )
        width = state.rendering_config.get("width")
        height = state.rendering_config.get("height")
        if isinstance(width, int) and width > 0:
            result["width"] = width
        if isinstance(height, int) and height > 0:
            result["height"] = height
        result["loras"] = loras
        result["worldpack_id"] = state.worldpack_id
        result["turn_number"] = state.turn_number
        workflow_file = state.rendering_config.get("workflow_file")
        if isinstance(workflow_file, str) and workflow_file:
            result["workflow_file"] = workflow_file
        return result




_ALLOWED_FOCUS_REGIONS = {
    "face",
    "eyes",
    "hands",
    "outfit",
    "legs",
    "feet",
    "buttocks",
    "hips",
    "back",
    "chest",
    "full_body",
    "interaction",
}


def _apply_visual_focus(vst: JSONObject, state: WorldState) -> None:
    """Validate visual intent and derive deterministic framing requirements."""
    raw = vst.get("visual_focus")
    if raw is None:
        return
    if not isinstance(raw, dict):
        raise ValueError("VST visual_focus must be an object")
    subject_id = raw.get("subject_id")
    region = raw.get("target_region")
    priority = raw.get("priority", "primary")
    if not isinstance(subject_id, str) or not subject_id:
        raise ValueError("visual focus subject must be a non-empty string")
    visible_ids = {
        str(subject.get("entity_id"))
        for subject in vst.get("subjects", [])
        if isinstance(subject, dict) and subject.get("entity_id")
    }
    if subject_id not in visible_ids:
        raise ValueError(f"visual focus subject {subject_id!r} is not visible in scene")
    if not isinstance(region, str) or region not in _ALLOWED_FOCUS_REGIONS:
        raise ValueError(f"unsupported visual focus region: {region!r}")
    if priority not in {"primary", "secondary"}:
        raise ValueError(f"unsupported visual focus priority: {priority!r}")

    camera = vst.get("camera")
    if not isinstance(camera, dict):
        raise ValueError("VST camera must be an object")
    selected = select_focus_camera(
        state,
        entity_id=subject_id,
        focus_region=region,
    )
    if selected is not None:
        camera.update(selected)
        return
    _legacy_focus_requirements(camera, region)


def _apply_action_library(vst: JSONObject, state: WorldState) -> None:
    """Expand VST semantic action ids through the Worldpack action catalog."""
    action = vst.get("action")
    if not isinstance(action, dict):
        return
    library = state.rendering_config.get("action_library")
    if not isinstance(library, dict) or not isinstance(library.get("actions"), dict):
        return
    action["resolved_tags"] = resolve_action_tags(
        state,
        action_id=str(action.get("action_id", "")) or None,
        description=str(action.get("description", "")),
        interaction=str(action.get("interaction", "")),
    )


def _legacy_focus_requirements(camera: JSONObject, region: str) -> None:
    """Fallback framing for Worldpacks without a camera library."""
    positive: list[str] = []
    negative: list[str] = []
    if region == "feet":
        positive = ["feet clearly visible", "both feet fully in frame", "visual focus on feet"]
        negative = ["cropped feet", "feet out of frame", "malformed feet", "extra toes", "missing toes"]
    elif region == "hands":
        positive = ["hands clearly visible", "both hands in frame", "visual focus on hands"]
        negative = ["cropped hands", "hands out of frame"]
    elif region == "face":
        positive = ["face clearly visible", "visual focus on face"]
        negative = ["face out of frame", "obscured face"]
    elif region == "eyes":
        positive = ["eyes clearly visible", "visual focus on eyes"]
        negative = ["obscured eyes"]
    elif region == "legs":
        positive = ["legs clearly visible", "visual focus on legs"]
        negative = ["legs out of frame"]
    elif region == "buttocks":
        positive = ["lower body clearly visible", "rear lower-body emphasis"]
        negative = ["lower body cropped", "rear view obscured"]
    elif region == "hips":
        positive = ["hips clearly visible", "hip emphasis"]
        negative = ["hips cropped"]
    elif region == "back":
        positive = ["back clearly visible", "rear body emphasis"]
        negative = ["back obscured"]
    elif region == "chest":
        positive = ["upper torso clearly visible"]
        negative = ["upper torso cropped"]
    elif region == "outfit":
        positive = ["full outfit clearly visible", "visual focus on outfit"]
        negative = ["cropped outfit"]
    elif region == "full_body":
        positive = ["full body in frame"]
        negative = ["cropped body"]
    elif region == "interaction":
        positive = ["interaction clearly framed"]
    camera["framing_requirements"] = positive
    camera["negative_framing_requirements"] = negative


def _validate_player_scene_scope(vst: JSONObject, state: WorldState) -> None:
    """Enforce player-local visual scenes and reject implicit cutaways."""
    location = vst.get("location")
    if not isinstance(location, dict):
        raise ValueError("VST location must be an object")
    location_id = location.get("location_id")
    if location_id != state.player.location_id:
        raise ValueError(
            f"VST location {location_id!r} must match player location {state.player.location_id!r}"
        )

    player_id = str(state.player.entity_id)
    for subject in vst.get("subjects", []):
        if not isinstance(subject, dict):
            raise ValueError("VST subjects must be objects")
        entity_id = subject.get("entity_id")
        if entity_id == player_id:
            continue
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError("VST subject entity_id must be a non-empty string")
        npc = state.get_npc(entity_id)
        if npc is None:
            raise ValueError(f"unknown VST subject: {entity_id}")
        if not npc.is_alive or not npc.is_present or npc.location_id != state.player.location_id:
            raise ValueError(
                f"NPC {entity_id!r} is not present at player location {state.player.location_id!r}"
            )

def _default_loras(state: WorldState) -> list[tuple[str, float]]:
    """Return worldpack-wide LoRA layers applied to all scene renders."""
    raw = state.rendering_config.get("default_loras", [])
    if not isinstance(raw, list):
        raise ValueError("rendering default_loras must be a list")
    result: list[tuple[str, float]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("rendering default_loras entries must be objects")
        alias = item.get("name")
        weight = item.get("weight", 1.0)
        if not isinstance(alias, str) or not alias:
            raise ValueError("rendering default_loras name must be a non-empty string")
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise ValueError("rendering default_loras weight must be numeric")
        result.append((alias, float(weight)))
    return result


def _lora_registry(state: WorldState) -> dict[str, str]:
    """Execute the lora registry operation."""
    raw = state.rendering_config.get("lora_registry", {})
    if not isinstance(raw, dict):
        raise ValueError("rendering lora_registry must be a mapping")
    result: dict[str, str] = {}
    for alias, filename in raw.items():
        if not isinstance(alias, str) or not isinstance(filename, str):
            raise ValueError("rendering lora_registry entries must be strings")
        result[alias] = filename
    return result


def _strip_lora_tags(text: str) -> tuple[str, list[tuple[str, float]]]:
    """Execute the strip lora tags operation."""
    found = [(match.group(1), float(match.group(2))) for match in _LORA_TAG_RE.finditer(text)]
    cleaned = _LORA_TAG_RE.sub("", text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,")
    return cleaned, found


def _append_resolved_lora(
    output: list[dict[str, object]],
    seen: set[tuple[str, float]],
    registry: dict[str, str],
    alias: str,
    weight: float,
) -> None:
    """Execute the append resolved lora operation."""
    filename = registry.get(alias)
    if filename is None:
        raise ValueError(f"unknown LoRA alias: {alias}")
    key = (filename, weight)
    if key in seen:
        return
    seen.add(key)
    output.append({"name": filename, "weight": weight})


def _apply_authoritative_outfits(vst: JSONObject, state: WorldState) -> None:
    """Replace all LLM-provided outfit/body visibility fields with WorldState data."""
    for subject in vst.get("subjects", []):
        if not isinstance(subject, dict):
            continue
        entity_id = subject.get("entity_id")
        if entity_id == "player":
            outfit = state.player.outfit
        elif isinstance(entity_id, str):
            npc = state.get_npc(entity_id)
            if npc is None:
                continue
            outfit = npc.outfit
        else:
            continue
        subject["outfit_visible"] = [
            {
                "item": item.name,
                "coverage": item.coverage,
                "state": "worn",
                "material": item.material or "",
                "color": item.color or "",
            }
            for item in outfit
        ]
        subject["body_state"] = _body_state(outfit)
        subject["skin_visible"] = _skin_visible(outfit)


_FOOTWEAR_TOKENS = ("shoe", "shoes", "heel", "heels", "stiletto", "pump", "pumps", "sandal", "sandals")


def _apply_transient_visual_state(vst: JSONObject) -> None:
    """Apply frame-only visual changes without mutating authoritative WorldState."""
    action = vst.get("action")
    if not isinstance(action, dict):
        return
    marker = action.get("narrative_moment")
    if marker not in {"transient_footwear_removed", "transient_bare_feet"}:
        return
    focus = vst.get("visual_focus")
    target_id = focus.get("subject_id") if isinstance(focus, dict) else None
    for subject in vst.get("subjects", []):
        if not isinstance(subject, dict):
            continue
        if isinstance(target_id, str) and subject.get("entity_id") != target_id:
            continue
        visible = subject.get("outfit_visible")
        if isinstance(visible, list):
            subject["outfit_visible"] = [
                item
                for item in visible
                if not (
                    isinstance(item, dict)
                    and any(
                        token in str(item.get("item", "")).casefold()
                        for token in _FOOTWEAR_TOKENS
                    )
                )
            ]
        skin = [str(region) for region in subject.get("skin_visible", []) if isinstance(region, str)]
        if "feet" not in skin:
            skin.append("feet")
        subject["skin_visible"] = skin
        pose_tags = [str(tag) for tag in subject.get("pose_tags", []) if isinstance(tag, str)]
        if "bare feet" not in pose_tags:
            pose_tags.append("bare feet")
        subject["pose_tags"] = pose_tags
        return


def _body_state(outfit: list[OutfitItem]) -> str:
    """Execute the body state operation."""
    anatomical = any(item.slot in {"torso", "legs"} for item in outfit)
    if not anatomical:
        return "clothed" if outfit else "fully_nude"
    torso = _coverage(outfit, "torso")
    legs = _coverage(outfit, "legs")
    if torso == 0 and legs == 0:
        return "fully_nude"
    if torso == 0:
        return "topless"
    if legs == 0:
        return "bottomless"
    if torso < 0.5 or legs < 0.5:
        return "revealing"
    return "clothed"


def _skin_visible(outfit: list[OutfitItem]) -> list[str]:
    """Execute the skin visible operation."""
    if not any(item.slot in {"torso", "legs"} for item in outfit):
        return []
    torso = _coverage(outfit, "torso")
    legs = _coverage(outfit, "legs")
    regions: list[str] = []
    if torso < 1:
        regions.extend(["arms", "shoulders", "midriff"])
    if legs < 1:
        regions.append("legs")
    return regions


def _coverage(outfit: list[OutfitItem], slot: str) -> float:
    """Execute the coverage operation."""
    coverage = 0.0
    for item in sorted((entry for entry in outfit if entry.slot == slot), key=lambda entry: entry.layer):
        coverage += item.coverage * (1.0 - coverage)
    return coverage
