"""Turn diagnostics collection."""
from __future__ import annotations
import hashlib
from epos_v3.domain.checks import CheckProposal, ResolvedCheck, CheckType
from epos_v3.domain.world import WorldState

class DiagnosticsService:
    """Build a deterministic diagnostic snapshot without changing state."""
    def collect(self, old_state: WorldState, new_state: WorldState, proposal: CheckProposal, resolved: ResolvedCheck, scene_text: str) -> dict[str, object]:
        """Collect turn-level diagnostics."""
        state_json = new_state.model_dump_json()
        return {
            "turn_number": new_state.turn_number,
            "player_location": old_state.player.location_id,
            "present_npcs": [n.name for n in old_state.present_npcs()],
            "check_type": proposal.check_type.value,
            "pool_size": resolved.pool_size,
            "dice_pool": list(resolved.dice.pool),
            "successes": resolved.dice.successes,
            "outcome": "no_check" if proposal.check_type == CheckType.NO_CHECK else resolved.outcome.value,
            "player_choice": resolved.choice,
            "narration_length": len(scene_text),
            "outfit_coverage_torso": old_state.player.get_coverage_by_slot("torso"),
            "outfit_coverage_legs": old_state.player.get_coverage_by_slot("legs"),
            "state_hash": hashlib.sha256(state_json.encode()).hexdigest(),
            "npc_emotional_states": {n.name: dict(n.emotional_state) for n in old_state.present_npcs()},
            "npc_intentions": {n.name: [i.action for i in n.intentions] for n in old_state.present_npcs()},
        }
