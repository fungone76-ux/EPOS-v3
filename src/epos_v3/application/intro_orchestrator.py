"""Turn orchestrator extension for deterministic Worldpack introductions."""

from __future__ import annotations

import copy
import time

from epos_v3.domain.world import WorldState

from .orchestrator import TurnOrchestrator
from .world_intro import IntroResult, WorldIntroService


class IntroTurnOrchestrator(TurnOrchestrator):
    """Run a Worldpack-authored intro before delegating to normal LLM gameplay."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        """Create the normal orchestrator plus the deterministic intro service."""
        super().__init__(*args, **kwargs)
        self.intro_service = WorldIntroService()

    async def play_turn(self, session_id: str, player_input: str) -> dict[str, object]:
        """Consume one intro step when active, otherwise execute the normal turn pipeline."""
        state = await self.store.load(session_id)
        if state is None:
            raise ValueError(f"Session not found: {session_id}")
        if self.intro_service.current_step(state) is None:
            return await super().play_turn(session_id, player_input)
        return await self._play_intro_turn(state, player_input)

    async def _play_intro_turn(
        self,
        state: WorldState,
        player_input: str,
    ) -> dict[str, object]:
        """Resolve, validate, render and commit one deterministic introduction step."""
        start = time.monotonic()
        candidate = copy.deepcopy(state)
        resolved = self.intro_service.resolve(candidate, player_input)
        if resolved is None:
            return await super().play_turn(state.session_id, player_input)

        candidate.turn_number += 1
        if self.world_rules is not None:
            self.world_rules.refresh_state_missions(candidate)
        validated = WorldState.model_validate(candidate.model_dump(mode="python"))

        visual_contract, visual_error = self._compile_intro_visual(resolved, validated)
        image_path: str | None = None
        if visual_contract and self.renderer.is_available():
            try:
                image_path = await self.renderer.render(visual_contract)
            except Exception as exc:
                visual_error = str(exc)

        await self.store.save(validated.session_id, validated)
        duration_ms = int((time.monotonic() - start) * 1000)
        return {
            "turn_number": validated.turn_number,
            "narration": resolved.narration,
            "image_path": image_path,
            "visual_prompt": visual_contract.get("prompt"),
            "visual_negative_prompt": visual_contract.get("negative_prompt"),
            "visual_loras": visual_contract.get("loras", []),
            "visual_error": visual_error,
            "outcome": "no_check",
            "dice": None,
            "intro": {
                "step_id": resolved.step_id,
                "focus_npc_id": resolved.focus_npc_id,
                "completed": resolved.completed,
            },
            "initiatives": [],
            "available_events": (
                []
                if not resolved.completed or self.world_rules is None
                else self.world_rules.available_state_events(validated)
            ),
            "diagnostics": {"intro_step": resolved.step_id},
            "duration_ms": duration_ms,
        }

    def _compile_intro_visual(
        self,
        resolved: IntroResult,
        state: WorldState,
    ) -> tuple[dict[str, object], str | None]:
        """Compile only structured intro VST; never ask the LLM for a prompt."""
        if not resolved.vst:
            return {}, None
        try:
            return self._compile_visual(resolved.vst, state), None
        except Exception as exc:
            return {}, str(exc)
