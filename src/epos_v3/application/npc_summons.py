"""Deterministic NPC summon handling from explicit player calls."""

from __future__ import annotations

import copy
import re

from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.world import WorldState

_CALL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(chiam[aoie]|chiama|chiamo|chiamare|fai\s+venire|fate\s+venire)\b", re.IGNORECASE),
    re.compile(r"\b(vieni\s+qui|raggiungimi|raggiungetemi|puoi\s+venire|potresti\s+venire)\b", re.IGNORECASE),
    re.compile(r"\b(mi\s+hai\s+chiamat[oa]|ti\s+ho\s+chiamat[oa])\b", re.IGNORECASE),
)


def apply_explicit_npc_summon(
    state: WorldState,
    proposal: CheckProposal,
    player_input: str,
) -> WorldState:
    """Move explicitly called target NPCs to the player's current location.

    The move is authoritative Python state handling. Merely mentioning or observing
    a remote NPC is not enough: the player's text must contain a clear summon/call
    cue and the NPC must already be a resolved proposal target.
    """
    if not _is_explicit_summon(player_input):
        return state
    if not proposal.target_ids:
        return state

    moved = copy.deepcopy(state)
    changed = False
    player_location = moved.player.location_id
    for target_id in proposal.target_ids:
        npc = moved.get_npc(target_id)
        if npc is None or not npc.is_alive or not npc.is_present:
            continue
        if npc.location_id == player_location:
            continue
        old_location = moved.locations.get(npc.location_id)
        if old_location is not None:
            old_location.npcs_present = [
                npc_id for npc_id in old_location.npcs_present if npc_id != target_id
            ]
        npc.location_id = player_location
        new_location = moved.locations.get(player_location)
        if new_location is not None and target_id not in new_location.npcs_present:
            new_location.npcs_present.append(target_id)
        changed = True

    if not changed:
        return state
    return WorldState.model_validate(moved.model_dump(mode="python"))


def _is_explicit_summon(player_input: str) -> bool:
    """Return whether player wording clearly asks a named NPC to come over."""
    normalized = " ".join(player_input.split())
    return any(pattern.search(normalized) for pattern in _CALL_PATTERNS)
