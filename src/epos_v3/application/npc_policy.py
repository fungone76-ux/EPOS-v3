"""Autonomous NPC policy: perceive, reason and decide initiative."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from epos_v3.domain.entities import Intention, NPCEntity, RhythmConfig
from epos_v3.domain.events import TurnEvent


class LongTermMemoryPort(Protocol):
    """Port used by an agent to store and recall long-term memories."""

    def add(self, text: str, turn: int, tags: list[str], importance: int) -> None:
        """Store one long-term memory."""
        ...

    def recall(self, context: str, n: int = 5) -> list[str]:
        """Recall memories relevant to one context."""
        ...




class LongTermMemoryProviderPort(Protocol):
    """Resolve the external long-term memory store for one NPC."""

    def for_npc(self, session_id: str, npc_id: str) -> LongTermMemoryPort:
        """Return the long-term memory store for one session/NPC pair."""
        ...

@dataclass(frozen=True)
class NPCPolicy:
    """Deterministic NPC policy built around the EPOS four-step lifecycle."""

    def perceive(
        self,
        npc: NPCEntity,
        event: TurnEvent,
        memory_store: LongTermMemoryPort | None = None,
    ) -> None:
        """Feed an event into NPC memory, emotions and relationships."""
        npc.perceived_events.append(event)
        from epos_v3.domain.entities import EmotionalAssociation, MemoryEntry

        entry = MemoryEntry(turn=event.turn, text=event.description, importance=event.importance)
        npc.short_term_memory.append(entry)
        npc.short_term_memory = npc.short_term_memory[-20:]
        if event.importance >= 8:
            npc.core_memories.append(entry)
        if memory_store is not None:
            memory_store.add(event.description, event.turn, list(event.tags), event.importance)

        if event.emotion:
            current = npc.emotional_state.get(event.emotion, 0)
            npc.emotional_state[event.emotion] = min(10, current + event.intensity)
            opposites = {"joy": "sadness", "anger": "trust", "fear": "arousal"}
            opposite = opposites.get(event.emotion)
            if opposite:
                npc.emotional_state[opposite] = max(
                    0, npc.emotional_state.get(opposite, 0) - event.intensity // 2
                )

        target = event.target_id or "player"
        npc.emotional_memory.setdefault(target, []).append(
            EmotionalAssociation(
                turn=event.turn,
                emotion=event.emotion or "neutral",
                intensity=event.importance,
                trigger=event.description,
            )
        )
        if event.relationship_delta:
            npc.update_relationship(target, event.relationship_delta, event.description)
        if target == "player":
            npc.last_player_action = event.description

    def reason(self, npc: NPCEntity, context: str, memory_store: LongTermMemoryPort | None = None) -> list[Intention]:
        """Create intentions from memories, emotions, goals and secrets."""
        if memory_store is not None:
            memory_store.recall(context, n=5)
        intentions: list[Intention] = []
        attraction = npc.emotional_state.get("attraction", 0)
        fear = npc.emotional_state.get("fear", 0)
        player_rel = npc.relationships.get("player")
        if player_rel is not None:
            if player_rel.resentment >= 7:
                intentions.append(
                    Intention(
                        action="confrontare_player",
                        reason=f"Risentimento accumulato ({player_rel.resentment})",
                        priority=player_rel.resentment,
                    )
                )
            if player_rel.suspicion >= 7:
                intentions.append(
                    Intention(
                        action="osservare_player",
                        reason=f"Sospetto accumulato ({player_rel.suspicion})",
                        priority=player_rel.suspicion,
                    )
                )
            if player_rel.fear >= 7:
                intentions.append(
                    Intention(
                        action="evitare_player",
                        reason=f"Paura relazionale ({player_rel.fear})",
                        priority=player_rel.fear,
                    )
                )
        if attraction >= 7:
            intentions.append(
                Intention(
                    action="avvicinarsi_player",
                    reason=f"Attrazione alta ({attraction})",
                    priority=min(10, attraction),
                )
            )
        if fear >= 7:
            intentions.append(Intention(action="fuggire", reason=f"Paura ({fear})", priority=fear))
        for secret in npc.secrets:
            if self._check_disclosure_condition(npc, secret.disclosure_condition, "player"):
                intentions.append(Intention(action="rivelare_segreto", reason=f"Trust sufficiente per rivelare {secret.secret_id}", priority=6))
        for goal in npc.goals:
            if goal not in npc.discoveries:
                intentions.append(Intention(action=f"perseguire_{goal}", reason=f"Goal non soddisfatto: {goal}", priority=5))
        npc.intentions = sorted(intentions, key=lambda item: item.priority, reverse=True)
        return list(npc.intentions)

    def should_act(self, npc: NPCEntity, rhythm: RhythmConfig, turn_number: int) -> bool:
        """Return whether the NPC is allowed to take initiative now."""
        if not npc.intentions or not npc.is_alive or not npc.is_present:
            return False
        if npc.last_action_turn is not None and turn_number - npc.last_action_turn < rhythm.minimum_turn_gap:
            return False
        max_priority = max(i.priority for i in npc.intentions)
        if max_priority >= 7:
            return True
        if any(value >= 8 for value in npc.emotional_state.values()) and max_priority >= 5:
            return True
        return max_priority >= rhythm.initiative_threshold

    def generate_response(self, npc: NPCEntity, player_input: str) -> str:
        """Generate a small deterministic response from current NPC state."""
        rel = npc.relationships.get("player")
        trust = rel.trust if rel else 0
        attraction = rel.attraction if rel else 0
        fear = rel.fear if rel else 0
        if "dimmi la verità" in player_input.lower():
            if trust >= 8 and attraction >= 7:
                return f"{npc.name} ti guarda negli occhi. 'Forse sei degno di saperla.'"
            if trust <= 2 or fear >= 6:
                return f"{npc.name} indietreggia. 'Non sono certa che tu possa portarne il peso.'"
            if npc.emotional_state.get("anger", 0) >= 7:
                return f"{npc.name} stringe i pugni. 'Non mi fido di te.'"
        return f"[{npc.speech_style}] {npc.name} risponde a '{player_input}'"

    @staticmethod
    def _check_disclosure_condition(npc: NPCEntity, condition: str, target_id: str) -> bool:
        """Evaluate the simple disclosure grammar defined by EPOS."""
        relationship = npc.relationships.get(target_id)
        if relationship is None:
            return False
        for raw in condition.split(" AND "):
            cond = raw.strip()
            if "trust >" in cond:
                try:
                    threshold = int(cond.split(">", 1)[1].strip())
                except ValueError:
                    return False
                if relationship.trust <= threshold:
                    return False
            elif "has " in cond:
                # Inventory belongs to the player/world, so this condition is
                # intentionally left unresolved here rather than guessed.
                continue
        return True
