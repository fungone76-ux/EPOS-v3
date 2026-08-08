"""Build narration-safe local context for scene generation."""

from __future__ import annotations

import json

from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.entities import NPCEntity
from epos_v3.domain.world import WorldState


def build_narration_snapshot(
    state: WorldState,
    proposal: CheckProposal,
    *,
    player_input: str = "",
    brief_social: bool = False,
    direct_social: bool = False,
    focused_interaction: bool = False,
    outfit_resolution: dict[str, object] | None = None,
) -> str:
    """Build player-local narration context without private NPC cognition."""
    local_npcs = {
        npc_id: narration_npc_view(npc)
        for npc_id, npc in state.npcs.items()
        if npc.is_alive
        and npc.is_present
        and npc.location_id == state.player.location_id
    }
    location = state.locations.get(state.player.location_id)
    payload: dict[str, object] = {
        "rule": (
            "Narrate only the player's local scene. Do not invent player choices, "
            "actions, companions, groups, missions, secrets, or remote NPC activity."
        ),
        "narration_mode": _narration_mode(brief_social, direct_social, focused_interaction),
        "narration_policy": _narration_policy(brief_social, direct_social, focused_interaction),
        "day": state.day,
        "phase": state.world_phase,
        "player": state.player.model_dump(mode="json"),
        "location": (
            location.model_dump(mode="json")
            if location is not None
            else {"location_id": state.player.location_id}
        ),
        "local_npcs": local_npcs,
        "raw_player_input": player_input,
        "authoritative_player_action": proposal.model_dump(mode="json"),
        "outfit_request_resolution": outfit_resolution or {},
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def narration_npc_view(npc: NPCEntity) -> dict[str, object]:
    """Expose observable/personality NPC data while withholding private cognition."""
    return {
        "entity_id": npc.entity_id,
        "name": npc.name,
        "archetype": npc.archetype,
        "personality": npc.personality,
        "speech_style": npc.speech_style,
        "location_id": npc.location_id,
        "is_present": npc.is_present,
        "outfit": [item.model_dump(mode="json") for item in npc.outfit],
        "conditions": list(npc.conditions),
    }


def _narration_mode(brief: bool, direct: bool, focused: bool) -> str:
    if brief:
        return "brief_social"
    if direct:
        return "direct_social"
    if focused:
        return "focused_interaction"
    return "standard"


def _narration_policy(brief: bool, direct: bool, focused: bool) -> dict[str, object]:
    if brief:
        return {
            "max_sentences": 2,
            "requirements": (
                "Answer the greeting or short social cue directly. The addressed NPC "
                "should reply naturally and may ask at most one short question. "
                "Omit environment and outfit exposition unless directly relevant."
            ),
        }
    if direct:
        return {
            "max_sentences": 2,
            "requirements": (
                "Reply directly to the player's exact line. Use at most one short physical "
                "reaction plus one concise NPC reply. Never exceed two sentences. Do not "
                "restate the location or outfit unless it changed. Do not repeat exposition "
                "and do not pivot to unrelated NPC goals."
            ),
        }
    if focused:
        return {
            "max_sentences": 2,
            "requirements": (
                "Describe only the immediate observable action and NPC reaction. Use at most "
                "two concise sentences. Do not expose private goals, desires, intentions, "
                "memories, or internal reasoning. Do not append an unrelated NPC initiative "
                "or repeat scene setup."
            ),
        }
    return {"max_sentences": None}
