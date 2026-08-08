"""Canonicalize LLM visual data against authoritative world state."""

from __future__ import annotations

import copy

from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState


_ALLOWED_ACTION_TYPES = {
    "dialogue",
    "action",
    "intimate_moment",
    "discovery",
    "transition",
    "combat",
}
_ALLOWED_INTENSITIES = {"neutral", "suggestive", "sensual", "erotic", "explicit"}


def canonicalize_vst(vst: JSONObject, state: WorldState) -> JSONObject:
    """Return a deep-copied VST with a complete authoritative visual sub-contract."""
    canonical = copy.deepcopy(vst)
    canonical["scene_id"] = _scene_id(canonical, state)
    canonical["location"] = _location(canonical.get("location"), state)
    canonical["subjects"] = _subjects(canonical.get("subjects"), state)
    canonical["action"] = _action(canonical.get("action"))
    canonical["camera"] = _camera(canonical.get("camera"))
    canonical["lighting"] = _lighting(canonical.get("lighting"))
    canonical["style"] = _style(canonical.get("style"), state)
    canonical["safety"] = _safety(canonical.get("safety"))
    canonical["visual_focus"] = _visual_focus(canonical.get("visual_focus"))
    canonical.setdefault("mutations", [])
    canonical.setdefault("dialogue", [])
    canonical.setdefault("visual", {})
    return canonical


def _scene_id(vst: JSONObject, state: WorldState) -> str:
    value = vst.get("scene_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"turn-{state.turn_number + 1}"


def _location(raw: object, state: WorldState) -> JSONObject:
    source = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    world_location = state.locations.get(state.player.location_id)
    source["location_id"] = state.player.location_id
    source["time_of_day"] = _text(source.get("time_of_day"), state.time_of_day.value)
    source["lighting"] = _text(source.get("lighting"), "ambient")
    source["atmosphere"] = _text(
        source.get("atmosphere"),
        (world_location.description or "") if world_location is not None else "",
    )
    tags = source.get("environment_tags")
    source["environment_tags"] = (
        [str(item) for item in tags if isinstance(item, str)]
        if isinstance(tags, list)
        else []
    )
    return source


def _subjects(raw: object, state: WorldState) -> list[JSONObject]:
    if not isinstance(raw, list):
        return []
    result: list[JSONObject] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        entity_id = item.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            continue
        subject = copy.deepcopy(item)
        outfit: list[OutfitItem] | None = None
        gender = "ambiguous"
        role = "focus"
        if entity_id == state.player.entity_id:
            outfit = state.player.outfit
            role = "protagonist"
        else:
            npc = state.get_npc(entity_id)
            if npc is not None:
                outfit = npc.outfit
                gender = npc.visual_gender
        subject["entity_id"] = entity_id
        subject["role"] = _choice(
            subject.get("role"),
            {"protagonist", "antagonist", "focus", "observer", "background"},
            role,
        )
        subject["gender"] = _choice(
            gender if gender in {"male", "female", "ambiguous"} else subject.get("gender"),
            {"male", "female", "ambiguous"},
            "ambiguous",
        )
        subject["pose"] = _text(subject.get("pose"), "natural standing pose")
        pose_tags = subject.get("pose_tags")
        subject["pose_tags"] = (
            [str(tag) for tag in pose_tags if isinstance(tag, str)]
            if isinstance(pose_tags, list)
            else []
        )
        if outfit is not None:
            subject["body_state"] = _body_state(outfit)
            subject["outfit_visible"] = _outfit_visible(outfit)
            subject["skin_visible"] = _skin_visible(outfit)
        else:
            subject["body_state"] = _choice(
                subject.get("body_state"),
                {"clothed", "revealing", "topless", "bottomless", "fully_nude"},
                "clothed",
            )
            subject.setdefault("outfit_visible", [])
            subject.setdefault("skin_visible", [])
        subject["expression"] = _text(subject.get("expression"), "")
        subject["gaze"] = _text(subject.get("gaze"), "")
        subject["focal"] = bool(subject.get("focal", role == "focus"))
        subject["distance_from_camera"] = _text(
            subject.get("distance_from_camera"),
            "medium",
        )
        subject["position_relative_to_focus"] = _text(
            subject.get("position_relative_to_focus"),
            "front",
        )
        result.append(subject)
    return result


def _action(raw: object) -> JSONObject:
    source = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    source["type"] = _choice(source.get("type"), _ALLOWED_ACTION_TYPES, "action")
    source["action_id"] = _text(source.get("action_id"), "")
    source["intimacy_id"] = _text(source.get("intimacy_id"), "none")
    source["description"] = _text(source.get("description"), "local narrative scene")
    source["interaction"] = _text(source.get("interaction"), "none")
    source["intensity"] = _choice(
        source.get("intensity"),
        _ALLOWED_INTENSITIES,
        "neutral",
    )
    source["narrative_moment"] = _text(source.get("narrative_moment"), "")
    return source


def _camera(raw: object) -> JSONObject:
    source = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    source["shot_type"] = _text(source.get("shot_type"), "medium_shot")
    source["angle"] = _text(source.get("angle"), "eye_level")
    source["orientation"] = _text(source.get("orientation"), "front")
    source["focus"] = _text(source.get("focus"), "main subject")
    source["depth_of_field"] = _text(source.get("depth_of_field"), "shallow")
    source["background_blur"] = bool(source.get("background_blur", True))
    source["rule_of_thirds"] = bool(source.get("rule_of_thirds", True))
    return source


def _lighting(raw: object) -> JSONObject:
    source = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    source["primary"] = _text(source.get("primary"), "natural ambient light")
    source["secondary"] = _text(source.get("secondary"), "")
    source["rim_light"] = _text(source.get("rim_light"), "")
    source["shadows"] = _text(source.get("shadows"), "natural soft shadows")
    return source


def _style(raw: object, state: WorldState) -> JSONObject:
    source = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    configured_style = state.rendering_config.get("visual_style_en")
    source["art_style"] = (
        configured_style.strip()
        if isinstance(configured_style, str) and configured_style.strip()
        else _text(source.get("art_style"), "cinematic realistic photography")
    )
    source["rendering"] = _text(source.get("rendering"), "detailed")
    source["color_palette"] = _text(source.get("color_palette"), "natural")
    source["mood"] = _text(source.get("mood"), "contextual")
    lora = source.get("lora")
    source["lora"] = [item for item in lora if isinstance(item, dict)] if isinstance(lora, list) else []
    source["model"] = _text(source.get("model"), "default")
    return source


def _safety(raw: object) -> JSONObject:
    source = copy.deepcopy(raw) if isinstance(raw, dict) else {}
    source["nudity_level"] = _text(source.get("nudity_level"), "none")
    source["explicit_tags"] = bool(source.get("explicit_tags", False))
    source["policy_compliant"] = bool(source.get("policy_compliant", True))
    source["outfit_authoritative"] = True
    return source


def _visual_focus(raw: object) -> JSONObject | None:
    if not isinstance(raw, dict):
        return None
    subject_id = raw.get("subject_id")
    target_region = raw.get("target_region")
    if not isinstance(subject_id, str) or not subject_id:
        return None
    allowed = {"face", "eyes", "hands", "outfit", "legs", "feet", "buttocks", "hips", "back", "chest", "full_body", "interaction"}
    if target_region not in allowed:
        return None
    return {
        "subject_id": subject_id,
        "target_region": target_region,
        "priority": _choice(raw.get("priority"), {"primary", "secondary"}, "primary"),
        "gaze_source": _text(raw.get("gaze_source"), "camera"),
    }


def _outfit_visible(outfit: list[OutfitItem]) -> list[JSONObject]:
    return [
        {
            "item": item.name,
            "coverage": item.coverage,
            "state": "worn",
            "material": item.material or "",
            "color": item.color or "",
        }
        for item in outfit
    ]


def _body_state(outfit: list[OutfitItem]) -> str:
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
    if not any(item.slot in {"torso", "legs"} for item in outfit):
        return []
    regions: list[str] = []
    if _coverage(outfit, "torso") < 1:
        regions.extend(["arms", "shoulders", "midriff"])
    if _coverage(outfit, "legs") < 1:
        regions.append("legs")
    return regions


def _coverage(outfit: list[OutfitItem], slot: str) -> float:
    coverage = 0.0
    for item in sorted(
        (entry for entry in outfit if entry.slot == slot),
        key=lambda entry: entry.layer,
    ):
        coverage += item.coverage * (1.0 - coverage)
    return coverage


def _text(value: object, default: str) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else default


def _choice(value: object, allowed: set[str], default: str) -> str:
    return value if isinstance(value, str) and value in allowed else default
