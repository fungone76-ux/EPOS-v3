"""Deterministic Worldpack-authored pose selection."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib

from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState


def select_pose(
    state: WorldState,
    *,
    entity_id: str,
    category: str,
    focus_region: str | None = None,
) -> tuple[str, list[str]] | None:
    """Select one authored pose deterministically from the Worldpack library."""
    library = state.rendering_config.get("pose_library")
    if not isinstance(library, Mapping):
        return None
    if library.get("library_type") == "pose":
        return _select_v1(
            library,
            state=state,
            entity_id=entity_id,
            category=category,
            key=focus_region,
        )
    return _select_legacy(
        library,
        state=state,
        entity_id=entity_id,
        category=category,
        key=focus_region,
    )


def _select_v1(
    library: Mapping[object, object],
    *,
    state: WorldState,
    entity_id: str,
    category: str,
    key: str | None,
) -> tuple[str, list[str]] | None:
    poses = library.get("poses")
    if not isinstance(poses, Mapping):
        return None
    candidate_ids: list[str] = []
    if category == "default":
        candidate_ids = [str(pose_id) for pose_id in poses]
    elif category == "focus" and key is not None:
        raw_sets = library.get("focus_sets")
        if isinstance(raw_sets, Mapping):
            candidate_ids = _string_list(raw_sets.get(key))
    elif category == "actions" and key is not None:
        raw_compat = library.get("action_compatibility")
        if isinstance(raw_compat, Mapping):
            candidate_ids = _string_list(raw_compat.get(key))
    candidate_ids = [pose_id for pose_id in candidate_ids if pose_id in poses]
    if not candidate_ids:
        return None
    pose_id = _stable_pick(
        candidate_ids,
        state=state,
        entity_id=entity_id,
        category=category,
        key=key,
    )
    raw_pose = poses.get(pose_id)
    if not isinstance(raw_pose, Mapping):
        return None
    tags = _string_list(raw_pose.get("tags"))
    prompt_raw = raw_pose.get("prompt")
    prompt = str(prompt_raw).strip() if isinstance(prompt_raw, str) else ", ".join(tags)
    if not prompt:
        return None
    return prompt, tags


def _select_legacy(
    library: Mapping[object, object],
    *,
    state: WorldState,
    entity_id: str,
    category: str,
    key: str | None,
) -> tuple[str, list[str]] | None:
    raw_entries = _legacy_entries(library, category=category, key=key)
    entries = [entry for entry in raw_entries if _valid_legacy(entry)]
    if not entries:
        return None
    indices = [str(index) for index in range(len(entries))]
    selected_index = int(
        _stable_pick(
            indices,
            state=state,
            entity_id=entity_id,
            category=category,
            key=key,
        )
    )
    selected = entries[selected_index]
    prompt = str(selected["prompt"]).strip()
    return prompt, _string_list(selected.get("tags"))


def _stable_pick(
    choices: list[str],
    *,
    state: WorldState,
    entity_id: str,
    category: str,
    key: str | None,
) -> str:
    seed = (
        f"{state.worldpack_id}:{state.turn_number}:{state.player.location_id}:"
        f"{entity_id}:{category}:{key or ''}"
    )
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return choices[int.from_bytes(digest[:8], "big") % len(choices)]


def _legacy_entries(
    library: Mapping[object, object], *, category: str, key: str | None
) -> list[JSONObject]:
    raw_category = library.get(category)
    if category == "default":
        return _object_list(raw_category)
    if not isinstance(raw_category, Mapping) or key is None:
        return []
    return _object_list(raw_category.get(key))


def _object_list(value: object) -> list[JSONObject]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _valid_legacy(entry: JSONObject) -> bool:
    prompt = entry.get("prompt")
    tags = entry.get("tags", [])
    return (
        isinstance(prompt, str)
        and bool(prompt.strip())
        and isinstance(tags, list)
        and all(isinstance(tag, str) for tag in tags)
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]
