"""Integrate authoritative NPC initiatives into narration and memory."""

from __future__ import annotations

from epos_v3.domain.events import TurnEvent
from epos_v3.domain.world import WorldState


class InitiativeIntegrationService:
    """Record NPC initiatives as world events and compose visible narration."""

    def record(self, state: WorldState, initiatives: list[dict[str, str]]) -> None:
        """Record each initiative for the actor and local witnesses exactly once.

        Args:
            state: Mutable authoritative world state.
            initiatives: Already-decided and optionally narrated NPC initiatives.
        """
        for initiative in initiatives:
            npc_id = initiative["npc_id"]
            actor = state.get_npc(npc_id)
            if actor is None:
                continue
            description = initiative.get("narration") or (
                f"{actor.name} prende l'iniziativa: {initiative['action']}."
            )
            event = TurnEvent(
                turn=state.turn_number,
                type="npc_initiative",
                description=description,
            )
            for observer in state.present_npcs():
                if observer.location_id != actor.location_id:
                    continue
                if self._already_recorded(observer, event):
                    continue
                observer.perceive(event)

    def compose(self, base_narration: str, initiatives: list[dict[str, str]]) -> str:
        """Append initiative narration to the base scene without altering authority.

        Args:
            base_narration: Narration already produced for the player turn.
            initiatives: NPC initiatives already decided by Python.

        Returns:
            A single narration string suitable for presentation.
        """
        base = base_narration.strip()
        initiative_lines = [
            item["narration"].strip()
            for item in initiatives
            if item.get("narration", "").strip()
        ]
        parts = [base] if base else []
        seen = {base} if base else set()
        for line in initiative_lines:
            if line in seen:
                continue
            seen.add(line)
            parts.append(line)
        return "\n\n".join(parts)

    @staticmethod
    def _already_recorded(observer: object, event: TurnEvent) -> bool:
        """Execute the already recorded operation."""
        perceived_events = getattr(observer, "perceived_events", [])
        return any(
            previous.turn == event.turn
            and previous.type == event.type
            and previous.description == event.description
            for previous in perceived_events
        )
