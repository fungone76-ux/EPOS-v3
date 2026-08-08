"""Deterministic Worldpack-authored camera selection."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib

from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState


def select_focus_camera(
    state: WorldState,
    *,
    entity_id: str,
    focus_region: str,
) -> JSONObject | None:
    """Select and expand a camera recipe for one visual focus region."""
    library = state.rendering_config.get("camera_library")
    if not isinstance(library, Mapping):
        return None
    cameras = library.get("cameras")
    focus_sets = library.get("focus_sets")
    if not isinstance(cameras, Mapping) or not isinstance(focus_sets, Mapping):
        return None
    raw_ids = focus_sets.get(focus_region)
    if not isinstance(raw_ids, list):
        return None
    ids = [str(value) for value in raw_ids if isinstance(value, str) and value in cameras]
    if not ids:
        return None
    seed = (
        f"{state.worldpack_id}:{state.turn_number}:{state.player.location_id}:"
        f"{entity_id}:camera:{focus_region}"
    )
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    camera_id = ids[int.from_bytes(digest[:8], "big") % len(ids)]
    raw_camera = cameras.get(camera_id)
    if not isinstance(raw_camera, Mapping):
        return None
    result: JSONObject = {
        "shot_type": str(raw_camera.get("shot_type", "medium_shot")),
        "angle": str(raw_camera.get("angle", "eye_level")),
        "orientation": str(raw_camera.get("orientation", "frontal")),
        "depth_of_field": str(raw_camera.get("depth_of_field", "shallow")),
        "background_blur": bool(raw_camera.get("background_blur", True)),
    }
    framing_rules = library.get("framing_rules")
    if isinstance(framing_rules, Mapping):
        raw_rule = framing_rules.get(focus_region)
        if isinstance(raw_rule, Mapping):
            result["framing_requirements"] = _string_list(raw_rule.get("positive"))
            result["negative_framing_requirements"] = _string_list(raw_rule.get("negative"))
    return result


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]
