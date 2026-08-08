"""Context compression for long LLM snapshots."""
from __future__ import annotations
import json
from epos_v3.domain.world import WorldState


class SnapshotCompressor:
    """Keep the most useful world information inside an approximate token budget."""
    def compress(self, state: WorldState, max_tokens: int = 8000) -> str:
        """Build a snapshot and progressively reduce low-value history."""
        budget = max(1, max_tokens * 4)
        full = self._build_full_snapshot(state)
        if len(full) <= budget:
            return full
        compact = self._compact(state)
        compact_json = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        if len(compact_json) <= budget:
            return compact_json
        compact["history_digest"] = state.history_digest or ""
        compact["npcs"] = self._compact_npcs(state)
        result = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        return result[:budget]

    def _build_full_snapshot(self, state: WorldState) -> str:
        """Execute the build full snapshot operation."""
        return state.model_dump_json()

    @staticmethod
    def _compact(state: WorldState) -> dict[str, object]:
        """Execute the compact operation."""
        return {
            "session_id": state.session_id,
            "worldpack_id": state.worldpack_id,
            "turn_number": state.turn_number,
            "time_of_day": state.time_of_day.value,
            "day": state.day,
            "player": state.player.model_dump(mode="json"),
            "locations": {key: value.model_dump(mode="json") for key, value in state.locations.items()},
            "missions": {key: value.model_dump(mode="json") for key, value in state.missions.items()},
            "skill_definitions": state.skill_definitions,
            "history_digest": state.history_digest,
        }

    @staticmethod
    def _compact_npcs(state: WorldState) -> dict[str, object]:
        """Execute the compact npcs operation."""
        return {
            key: {
                "name": npc.name,
                "location_id": npc.location_id,
                "emotional_state": npc.emotional_state,
                "intentions": [item.model_dump(mode="json") for item in npc.intentions],
                "short_term_memory": [item.model_dump(mode="json") for item in npc.short_term_memory[-3:]],
                "relationships": {rid: rel.model_dump(mode="json") for rid, rel in npc.relationships.items()},
            }
            for key, npc in state.npcs.items()
        }
