"""Narrate already-decided NPC initiatives without changing world authority."""
from __future__ import annotations

import asyncio
import json
from typing import Protocol

from epos_v3.domain.world import WorldState


class InitiativeNarrationPort(Protocol):
    """Minimal narration capability required by the initiative service."""

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        """Narrate an already-authoritative NPC initiative."""
        ...


class InitiativeNarrationService:
    """Ask an LLM to narrate an NPC action already chosen by Python."""

    def __init__(self, llm: InitiativeNarrationPort) -> None:
        """Execute the init operation."""
        self._llm = llm

    async def narrate(
        self,
        state: WorldState,
        initiative: dict[str, str],
    ) -> dict[str, str]:
        """Return the same authoritative initiative plus contextual narration."""
        npc_id = initiative["npc_id"]
        npc = state.get_npc(npc_id)
        npc_name = npc.name if npc is not None else npc_id
        payload = {
            "rule": (
                "Narrate only the authoritative NPC action. "
                "Never choose, imply, or narrate a player action or response. "
                "Do not invent groups, companions, bystanders, relationships, memories, "
                "or events not explicitly present in this payload."
            ),
            "npc_id": npc_id,
            "npc_name": npc_name,
            "action": initiative["action"],
            "reason": initiative["reason"],
            "turn_number": state.turn_number,
            "day": state.day,
            "phase": state.world_phase,
            "location_id": npc.location_id if npc is not None else state.player.location_id,
        }
        try:
            narration = await asyncio.wait_for(
                self._llm.narrate_scene(json.dumps(payload, ensure_ascii=False), "npc_initiative"),
                timeout=120.0,
            )
        except Exception:
            narration = f"{npc_name} prende l'iniziativa: {initiative['action']}."

        return {
            "npc_id": npc_id,
            "action": initiative["action"],
            "reason": initiative["reason"],
            "narration": narration,
        }
