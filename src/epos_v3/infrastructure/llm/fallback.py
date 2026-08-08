"""Primary-to-secondary LLM fallback adapter."""

from __future__ import annotations

import logging

from epos_v3.application.ports import LLMPort
from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState

logger = logging.getLogger(__name__)


class FallbackLLM(LLMPort):
    """Use the secondary provider when the primary fails."""

    def __init__(self, primary: LLMPort, secondary: LLMPort) -> None:
        """Execute the init operation."""
        self.primary = primary
        self.secondary = secondary

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        """Use the secondary provider if phase-one generation fails."""
        try:
            return await self.primary.propose_check(snapshot, player_input)
        except Exception as exc:
            logger.warning("Primary LLM failed; using fallback: %s", exc)
            return await self.secondary.propose_check(snapshot, player_input)

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        """Use the secondary provider if narration fails."""
        try:
            return await self.primary.narrate_scene(snapshot, resolved_outcome)
        except Exception as exc:
            logger.warning("Primary LLM failed; using fallback: %s", exc)
            return await self.secondary.narrate_scene(snapshot, resolved_outcome)

    async def clarify(self, snapshot: str, player_input: str) -> str:
        """Use the secondary provider if clarification fails."""
        try:
            return await self.primary.clarify(snapshot, player_input)
        except Exception as exc:
            logger.warning("Primary LLM failed; using fallback: %s", exc)
            return await self.secondary.clarify(snapshot, player_input)

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        """Use the secondary provider if VST generation fails."""
        try:
            return await self.primary.generate_vst(scene_description, world_state)
        except Exception as exc:
            logger.warning("Primary LLM failed; using fallback: %s", exc)
            return await self.secondary.generate_vst(scene_description, world_state)
