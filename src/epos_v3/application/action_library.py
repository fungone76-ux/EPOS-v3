"""Resolve Worldpack-authored semantic action ids into stable visual tags."""

from __future__ import annotations

from collections.abc import Mapping

from epos_v3.domain.world import WorldState

_FACE_TAG_MARKERS = (
    "smile",
    "smiling",
    "expression",
    "mouth",
    "gaze",
    "eyes directed",
    "eye contact",
)


def resolve_action_tags(
    state: WorldState,
    *,
    action_id: str | None,
    description: str,
    interaction: str,
) -> list[str]:
    """Resolve an action id or alias using the Worldpack action catalog."""
    library = state.rendering_config.get("action_library")
    if not isinstance(library, Mapping):
        return []
    actions = library.get("actions")
    if not isinstance(actions, Mapping):
        return []
    selected_id = action_id if isinstance(action_id, str) and action_id in actions else None
    if selected_id is None:
        selected_id = _match_alias(actions, f"{description} {interaction}".casefold())
    if selected_id is None:
        fallback = library.get("defaults")
        if isinstance(fallback, Mapping):
            candidate = fallback.get("fallback_action_id")
            if isinstance(candidate, str) and candidate in actions:
                selected_id = candidate
    raw = actions.get(selected_id) if selected_id is not None else None
    if not isinstance(raw, Mapping):
        return []
    tags = raw.get("tags")
    if not isinstance(tags, list):
        return []
    result: list[str] = []
    for tag in tags:
        if not isinstance(tag, str) or not tag.strip():
            continue
        lowered = tag.casefold()
        if any(marker in lowered for marker in _FACE_TAG_MARKERS):
            continue
        if tag not in result:
            result.append(tag)
    return result


def _match_alias(actions: Mapping[object, object], text: str) -> str | None:
    matches: list[tuple[int, str]] = []
    for raw_id, raw_action in actions.items():
        if not isinstance(raw_id, str) or not isinstance(raw_action, Mapping):
            continue
        aliases = raw_action.get("aliases")
        if not isinstance(aliases, list):
            continue
        for alias in aliases:
            if not isinstance(alias, str):
                continue
            normalized = alias.casefold().strip()
            if normalized and normalized in text:
                matches.append((len(normalized), raw_id))
    if not matches:
        return None
    matches.sort(key=lambda item: (-item[0], item[1]))
    return matches[0][1]
