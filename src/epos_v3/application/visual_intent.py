"""Authoritative visual intent extraction from player input."""

from __future__ import annotations

import copy

from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState

from .camera_library import select_focus_camera
from .pose_library import select_pose


_REGION_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("piedi", "piede", "feet", "foot"), "feet"),
    (("gambe", "gamba", "legs", "leg"), "legs"),
    (("culo", "sedere", "fondoschiena", "buttocks", "butt"), "buttocks"),
    (("fianchi", "fianco", "hips", "hip"), "hips"),
    (("schiena", "dorso", "back"), "back"),
    (("petto", "seno", "chest", "breasts"), "chest"),
    (("mani", "mano", "hands", "hand"), "hands"),
    (("occhi", "occhio", "eyes", "eye"), "eyes"),
    (("viso", "volto", "face"), "face"),
)


_SHOE_REMOVAL_MARKERS = (
    "si toglie le scarpe",
    "toglie le scarpe",
    "si sfila le scarpe",
    "sfila le scarpe",
    "removing her shoes",
    "takes off her shoes",
)

_BARE_FEET_MARKERS = (
    "piedi nudi",
    "piede nudo",
    "bare feet",
    "barefoot",
)


def apply_visual_intent(
    vst: JSONObject,
    state: WorldState,
    proposal: CheckProposal,
    player_input: str,
) -> JSONObject:
    """Inject authoritative visual emphasis cues inferred from player input."""
    result = copy.deepcopy(vst)
    target_id = _target_subject_id(result, proposal)
    shoe_removal = _is_shoe_removal(player_input)
    bare_feet = _is_bare_feet(player_input)
    region = _infer_region(player_input)
    if region is None and (shoe_removal or bare_feet):
        region = "feet"
    if target_id is not None and region is not None:
        result["visual_focus"] = {
            "subject_id": target_id,
            "target_region": region,
            "priority": "primary",
            "gaze_source": "viewer",
        }
        _apply_focus_pose(
            result,
            target_id,
            region,
            state=state,
            shoe_removal=shoe_removal,
        )
        _apply_focus_camera(result, state, target_id, region)
        action = result.get("action")
        if isinstance(action, dict):
            if shoe_removal:
                action["description"] = "removing one high heel during conversation"
                action["interaction"] = "conversation"
                action["narrative_moment"] = "transient_footwear_removed"
            elif bare_feet:
                action["narrative_moment"] = "transient_bare_feet"
        return result
    _apply_variety_pose(result, state)
    return result


def _target_subject_id(vst: JSONObject, proposal: CheckProposal) -> str | None:
    if proposal.target_ids:
        return proposal.target_ids[0]
    subjects = vst.get("subjects")
    if not isinstance(subjects, list):
        return None
    for subject in subjects:
        if isinstance(subject, dict) and subject.get("entity_id") not in {None, "player"}:
            entity_id = subject.get("entity_id")
            if isinstance(entity_id, str):
                return entity_id
    return None


def _infer_region(player_input: str) -> str | None:
    lowered = player_input.casefold()
    for variants, region in _REGION_RULES:
        if any(token in lowered for token in variants):
            return region
    return None


def _is_shoe_removal(player_input: str) -> bool:
    lowered = player_input.casefold()
    return any(marker in lowered for marker in _SHOE_REMOVAL_MARKERS)


def _is_bare_feet(player_input: str) -> bool:
    lowered = player_input.casefold()
    return any(marker in lowered for marker in _BARE_FEET_MARKERS)


def _apply_focus_pose(
    vst: JSONObject,
    target_id: str,
    region: str,
    *,
    state: WorldState,
    shoe_removal: bool,
) -> None:
    subjects = vst.get("subjects")
    if not isinstance(subjects, list):
        return
    for subject in subjects:
        if not isinstance(subject, dict) or subject.get("entity_id") != target_id:
            continue
        if shoe_removal:
            selected = select_pose(
                state,
                entity_id=target_id,
                category="actions",
                focus_region="shoe_removal",
            )
            if selected is not None:
                subject["pose"], subject["pose_tags"] = selected
            return
        selected = select_pose(
            state,
            entity_id=target_id,
            category="focus",
            focus_region=region,
        )
        if selected is not None:
            subject["pose"], subject["pose_tags"] = selected
        return


def _apply_focus_camera(
    vst: JSONObject, state: WorldState, target_id: str, region: str
) -> None:
    """Apply a deterministic Worldpack-authored camera recipe for body focus."""
    camera = vst.get("camera")
    if not isinstance(camera, dict):
        return
    selected = select_focus_camera(
        state,
        entity_id=target_id,
        focus_region=region,
    )
    if selected is not None:
        camera.update(selected)
        return
    _apply_legacy_focus_camera(camera, region)


def _apply_legacy_focus_camera(camera: JSONObject, region: str) -> None:
    """Preserve camera behavior for Worldpacks without a camera catalog."""
    framing = [
        str(item)
        for item in camera.get("framing_requirements", [])
        if isinstance(item, str)
    ]
    if region == "legs":
        framing.extend(["leg emphasis", "include legs clearly in frame"])
        camera["shot_type"] = "medium_full_shot"
    elif region == "feet":
        framing.extend(["foot emphasis", "include feet clearly in frame"])
        camera["shot_type"] = "medium_full_shot"
    elif region == "buttocks":
        framing.extend(["buttocks clearly visible", "lower body emphasis"])
        camera["shot_type"] = "medium_full_shot"
        camera["orientation"] = "rear_three_quarter"
    elif region == "hips":
        framing.extend(["hips clearly visible", "hip emphasis"])
        camera["shot_type"] = "medium_full_shot"
    elif region == "back":
        framing.extend(["back clearly visible", "rear body emphasis"])
        camera["orientation"] = "rear_three_quarter"
    elif region == "chest":
        framing.extend(["upper torso clearly visible", "chest emphasis"])
        camera["shot_type"] = "medium_shot"
    else:
        framing.append(f"focus on {region}")
    camera["framing_requirements"] = list(dict.fromkeys(framing))


def _apply_variety_pose(vst: JSONObject, state: WorldState) -> None:
    subjects = vst.get("subjects")
    if not isinstance(subjects, list):
        return
    for subject in subjects:
        if not isinstance(subject, dict) or subject.get("entity_id") == "player":
            continue
        current_pose = str(subject.get("pose", "")).strip()
        if current_pose and current_pose != "natural standing pose":
            continue
        entity_id = str(subject.get("entity_id", ""))
        selected = select_pose(
            state,
            entity_id=entity_id,
            category="default",
        )
        if selected is None:
            continue
        pose, tags = selected
        subject["pose"] = pose
        existing = [str(item) for item in subject.get("pose_tags", []) if isinstance(item, str)]
        for tag in tags:
            if tag not in existing:
                existing.append(tag)
        subject["pose_tags"] = existing
