"""Deterministic Worldpack-authored introduction state machine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from epos_v3.application.camera_library import select_focus_camera
from epos_v3.application.pose_library import select_pose
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState


@dataclass(frozen=True)
class IntroStep:
    """One authored introduction step."""

    step_id: str
    kind: str
    target_npc_id: str
    narration: str
    dialogue: str
    action_id: str


@dataclass(frozen=True)
class IntroResult:
    """Resolved deterministic intro turn returned to the orchestrator."""

    step_id: str
    narration: str
    focus_npc_id: str
    vst: JSONObject
    completed: bool


class WorldIntroService:
    """Advance an optional Worldpack intro without delegating world state to the LLM."""

    ACTIVE_FLAG = "resort_intro_active"
    INDEX_FLAG = "resort_intro_index"
    COMPLETE_FLAG = "resort_intro_completed"
    PRESENTED_FLAG = "resort_intro_presented"

    def initialise(self, state: WorldState) -> None:
        """Initialise persistent flags only when an intro is authored."""
        if not self._steps(state):
            return
        state.global_flags.setdefault(self.ACTIVE_FLAG, True)
        state.global_flags.setdefault(self.INDEX_FLAG, 0)
        state.global_flags.setdefault(self.COMPLETE_FLAG, False)
        state.global_flags.setdefault(self.PRESENTED_FLAG, [])

    def current_step(self, state: WorldState) -> IntroStep | None:
        """Return the current input-gating step, or None once the intro is complete."""
        self.initialise(state)
        if not bool(state.global_flags.get(self.ACTIVE_FLAG, False)):
            return None
        if bool(state.global_flags.get(self.COMPLETE_FLAG, False)):
            return None
        steps = self._steps(state)
        index = int(state.global_flags.get(self.INDEX_FLAG, 0))
        if index < 0 or index >= len(steps):
            return None
        return self._step_from_row(steps[index], index)

    def resolve(self, state: WorldState, player_text: str) -> IntroResult | None:
        """Consume one input and reveal exactly one NPC introduction."""
        step = self.current_step(state)
        if step is None:
            return None
        steps = self._steps(state)
        current_index = int(state.global_flags.get(self.INDEX_FLAG, 0))

        if step.kind == "player_intro":
            state.global_flags["player_intro_text"] = player_text.strip()
            output_index = current_index + 1
        else:
            output_index = current_index

        if output_index >= len(steps):
            self._mark_complete(state, len(steps))
            return None

        output_step = self._step_from_row(steps[output_index], output_index)
        presented = self._string_list(state.global_flags.get(self.PRESENTED_FLAG, []))
        if output_step.target_npc_id and output_step.target_npc_id not in presented:
            presented.append(output_step.target_npc_id)
        state.global_flags[self.PRESENTED_FLAG] = presented

        next_index = output_index + 1
        completed = next_index >= len(steps)
        if completed:
            self._mark_complete(state, next_index)
        else:
            state.global_flags[self.INDEX_FLAG] = next_index
            state.global_flags[self.COMPLETE_FLAG] = False
            state.global_flags[self.ACTIVE_FLAG] = True

        return IntroResult(
            step_id=output_step.step_id,
            narration=self._compose_narration(output_step),
            focus_npc_id=output_step.target_npc_id,
            vst=self._build_vst(state, output_step),
            completed=completed,
        )

    @staticmethod
    def _step_from_row(row: Mapping[object, object], index: int) -> IntroStep:
        return IntroStep(
            step_id=str(row.get("id", f"step_{index}")),
            kind=str(row.get("kind", "npc_intro")),
            target_npc_id=str(row.get("target_npc_id", "")),
            narration=str(row.get("narration", "")),
            dialogue=str(row.get("dialogue", "")),
            action_id=str(row.get("action_id", "speaking_gesture")),
        )

    def _mark_complete(self, state: WorldState, next_index: int) -> None:
        state.global_flags[self.INDEX_FLAG] = next_index
        state.global_flags[self.COMPLETE_FLAG] = True
        state.global_flags[self.ACTIVE_FLAG] = False
        state.global_flags["resort_freeplay_unlocked"] = True

    @staticmethod
    def _compose_narration(step: IntroStep) -> str:
        parts = [part.strip() for part in (step.narration, step.dialogue) if part.strip()]
        return "\n\n".join(parts)

    def _build_vst(self, state: WorldState, step: IntroStep) -> JSONObject:
        npc = state.get_npc(step.target_npc_id)
        if npc is None:
            return {}
        pose = select_pose(
            state,
            entity_id=npc.entity_id,
            category="actions",
            focus_region=step.action_id,
        ) or select_pose(state, entity_id=npc.entity_id, category="default")
        pose_text, pose_tags = pose if pose is not None else ("natural posture", [])
        camera = select_focus_camera(
            state,
            entity_id=npc.entity_id,
            focus_region="full_body",
        ) or {}
        location = state.get_location(state.player.location_id)
        environment_tags = [location.description] if location and location.description else []
        return {
            "scene_id": f"intro-{step.step_id}-{state.turn_number}",
            "location": {
                "location_id": state.player.location_id,
                "time_of_day": state.world_phase,
                "lighting": "",
                "atmosphere": "welcoming",
                "environment_tags": environment_tags,
            },
            "subjects": [
                {
                    "entity_id": npc.entity_id,
                    "role": "focus",
                    "gender": npc.visual_gender,
                    "pose": pose_text,
                    "pose_tags": pose_tags,
                    "body_state": "clothed",
                    "outfit_visible": [],
                    "skin_visible": [],
                    "expression": "",
                    "gaze": "",
                    "focal": True,
                    "distance_from_camera": "medium",
                    "position_relative_to_focus": "front",
                }
            ],
            "action": {
                "type": "dialogue",
                "action_id": step.action_id,
                "intimacy_id": "none",
                "description": "character introduction",
                "interaction": "none",
                "intensity": "neutral",
                "narrative_moment": "introduction",
            },
            "camera": {
                "shot_type": str(camera.get("shot_type", "medium_full_shot")),
                "angle": str(camera.get("angle", "eye_level")),
                "orientation": str(camera.get("orientation", "frontal")),
                "focus": npc.entity_id,
                "depth_of_field": str(camera.get("depth_of_field", "shallow")),
                "background_blur": bool(camera.get("background_blur", True)),
                "rule_of_thirds": True,
                "framing_requirements": self._string_list(camera.get("framing_requirements", [])),
                "negative_framing_requirements": self._string_list(
                    camera.get("negative_framing_requirements", [])
                ),
            },
            "lighting": {"primary": "", "secondary": "", "rim_light": "", "shadows": ""},
            "style": {
                "art_style": "",
                "rendering": "",
                "color_palette": "",
                "mood": "",
                "lora": [],
                "model": "default",
            },
            "safety": {
                "nudity_level": "none",
                "explicit_tags": False,
                "policy_compliant": True,
                "outfit_authoritative": True,
            },
        }

    @staticmethod
    def _steps(state: WorldState) -> list[Mapping[object, object]]:
        """Read intro steps from generic mission metadata persisted by the loader."""
        mission_rows = state.gameplay_rules.get("missions", [])
        if not isinstance(mission_rows, list):
            return []
        for row in mission_rows:
            if not isinstance(row, Mapping):
                continue
            raw_steps = row.get("intro_steps")
            if not isinstance(raw_steps, list):
                continue
            return [step for step in raw_steps if isinstance(step, Mapping)]
        return []

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]
