"""Deterministic world-state to Visual Semantic Table compiler."""

from __future__ import annotations

from epos_v3.domain.entities import NPCEntity, Player
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.types import JSONObject
from .vst_models import VisualSemanticTable


class VSTGenerator:
    """Build a VST from authoritative game state, never from free-form LLM outfit data."""

    def generate(self, scene_description: str, scene_id: str, location_id: str, npcs: list[NPCEntity], player: Player | None) -> JSONObject:
        """Compile scene, subjects, mood, camera, lighting and safety into JSON-compatible data."""
        subjects = [self._compile_subject(npc) for npc in npcs if npc.is_present and npc.is_alive]
        if player is not None:
            subjects.append(self._compile_player(player))
        focus = subjects[0]["entity_id"] if subjects else ""
        for subject in subjects:
            subject["focal"] = subject["entity_id"] == focus
        model = VisualSemanticTable(
            scene_id=scene_id,
            location={"location_id": location_id, "time_of_day": "unspecified", "lighting": "natural", "atmosphere": "ambient", "environment_tags": []},
            subjects=subjects,
            action={"type": "dialogue", "description": scene_description, "interaction": "none", "intensity": "neutral", "narrative_moment": scene_description},
            camera={"shot_type": "medium_shot", "angle": "eye_level", "orientation": "front", "focus": focus, "depth_of_field": "shallow", "background_blur": True, "rule_of_thirds": True},
            lighting={"primary": "soft natural", "secondary": "", "rim_light": "", "shadows": "soft"},
            style={"art_style": "cinematic", "rendering": "detailed", "color_palette": "natural", "mood": "neutral", "lora": [], "model": "default"},
            safety={"nudity_level": self._scene_nudity(subjects), "explicit_tags": False, "policy_compliant": True, "outfit_authoritative": True},
        )
        return model.model_dump()

    def _compile_subject(self, npc: NPCEntity) -> JSONObject:
        """Compile an NPC subject directly from authoritative outfit data."""
        torso = self._coverage(npc.outfit, "torso")
        legs = self._coverage(npc.outfit, "legs")
        anatomical = any(item.slot in {"torso", "legs"} for item in npc.outfit)
        body_state = self._body_state(torso, legs) if anatomical else ("clothed" if npc.outfit else "fully_nude")
        subject: JSONObject = {
            "entity_id": npc.entity_id, "role": "focus", "gender": npc.visual_gender, "pose": "standing",
            "pose_tags": [], "body_state": body_state,
            "outfit_visible": [{"item": i.name, "coverage": i.coverage, "state": "worn", "material": i.material or "", "color": i.color or ""} for i in npc.outfit],
            "skin_visible": self._visible_regions(torso, legs) if anatomical else [], "expression": "neutral", "gaze": "looking_at_viewer",
            "focal": False, "distance_from_camera": "medium", "position_relative_to_focus": "front",
        }
        return self._apply_mood_mapping(npc, subject)

    def _compile_player(self, player: Player) -> JSONObject:
        """Compile the player subject using the same authoritative outfit rules."""
        torso = player.get_coverage_by_slot("torso")
        legs = player.get_coverage_by_slot("legs")
        anatomical = any(item.slot in {"torso", "legs"} for item in player.outfit)
        body_state = self._body_state(torso, legs) if anatomical else ("clothed" if player.outfit else "fully_nude")
        skin_visible = self._visible_regions(torso, legs) if anatomical else []
        return {"entity_id": str(player.entity_id), "role": "protagonist", "gender": player.visual_gender, "pose": "standing", "pose_tags": [], "body_state": body_state, "outfit_visible": [{"item": i.name, "coverage": i.coverage, "state": "worn", "material": i.material or "", "color": i.color or ""} for i in player.outfit], "skin_visible": skin_visible, "expression": "neutral", "gaze": "looking_at_viewer", "focal": False, "distance_from_camera": "medium", "position_relative_to_focus": "front"}

    @staticmethod
    def _coverage(outfit: list[OutfitItem], slot: str) -> float:
        """Execute the coverage operation."""
        coverage = 0.0
        for item in sorted((i for i in outfit if i.slot == slot), key=lambda i: i.layer):
            coverage += item.coverage * (1.0 - coverage)
        return coverage

    @staticmethod
    def _body_state(torso: float, legs: float) -> str:
        """Execute the body state operation."""
        if torso == 0 and legs == 0: return "fully_nude"
        if torso == 0: return "topless"
        if legs == 0: return "bottomless"
        if torso < 0.5 or legs < 0.5: return "revealing"
        return "clothed"

    @staticmethod
    def _visible_regions(torso: float, legs: float) -> list[str]:
        """Execute the visible regions operation."""
        regions: list[str] = []
        if torso < 1: regions.extend(["arms", "shoulders", "midriff"])
        if legs < 1: regions.append("legs")
        return regions

    @staticmethod
    def _scene_nudity(subjects: list[JSONObject]) -> str:
        """Execute the scene nudity operation."""
        order = {"clothed": 0, "revealing": 1, "topless": 2, "bottomless": 2, "fully_nude": 3}
        state = max((s["body_state"] for s in subjects), key=lambda value: order[value], default="clothed")
        return state

    def _apply_mood_mapping(self, npc: NPCEntity, subject: JSONObject) -> JSONObject:
        """Apply the explicit mood-to-VST rules from EPOS."""
        tags = subject.setdefault("pose_tags", [])
        state = npc.emotional_state
        if state.get("anger", 0) > 7:
            tags.extend(["aggressive_stance", "clenched_fists"]); subject["expression"] = "cold_stare"
        if state.get("attraction", 0) > 8:
            subject["distance_from_camera"] = "close_up"; subject["gaze"] = "looking_at_viewer"; tags.append("leaning_forward")
        if state.get("fear", 0) > 7:
            tags.extend(["defensive", "backing_away"]); subject["expression"] = "wide_eyes"
        if state.get("joy", 0) > 7:
            subject["expression"] = "radiant"; tags.append("open_arms")
        if state.get("suspicion", 0) > 7:
            subject["gaze"] = "sideways_glance"; tags.append("arms_crossed")
        if state.get("sadness", 0) > 6:
            subject["expression"] = "melancholic"; tags.append("slumped_shoulders")
        if state.get("arousal", 0) > 7:
            subject["gaze"] = "heavy_lidded"; tags.append("hip_cocked")
        if state.get("trust", 0) > 8:
            subject["distance_from_camera"] = "close_up"; tags.append("relaxed_posture"); subject["expression"] = "warm_smile"
        if state.get("resentment", 0) > 6:
            tags.extend(["turned_away", "tense_jaw"]); subject["gaze"] = "looking_away"
        if state.get("melancholy", 0) > 5:
            tags.append("gazing_into_distance")
        return subject
