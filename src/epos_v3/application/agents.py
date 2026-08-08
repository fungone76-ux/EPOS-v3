"""Autonomous NPC initiative and agent-to-agent communication."""

from __future__ import annotations

from collections.abc import Callable

from epos_v3.domain.entities import AgentMessage, NPCEntity, RhythmConfig
from .npc_policy import LongTermMemoryProviderPort, NPCPolicy
from epos_v3.domain.events import TurnEvent
from epos_v3.domain.world import WorldState


class AgentService:
    """Run the deterministic NPC perceive/reason/act cycle."""

    def __init__(
        self,
        policy: NPCPolicy | None = None,
        memory_provider: LongTermMemoryProviderPort | None = None,
    ) -> None:
        """Create the service with one policy and optional long-term memory provider."""
        self.policy = policy or NPCPolicy()
        self.memory_provider = memory_provider

    async def process_agents(self, state: WorldState) -> list[dict[str, str]]:
        """Process NPCs after a normal player action."""
        return await self._process(
            state,
            event_type="player_action",
            description_factory=lambda npc: npc.last_player_action or "",
        )

    async def process_time_advance(self, state: WorldState) -> list[dict[str, str]]:
        """Process NPCs after the player explicitly advances the world clock.

        The event is deliberately not labelled as a player action, so old
        player input is never perceived twice by NPC memory systems.
        """
        description = f"Il tempo avanza a giorno {state.day}, fase {state.world_phase}."
        return await self._process(
            state,
            event_type="time_advanced",
            description_factory=lambda _npc: description,
        )

    async def _process(
        self,
        state: WorldState,
        *,
        event_type: str,
        description_factory: Callable[[NPCEntity], str],
    ) -> list[dict[str, str]]:
        """Run one deterministic agent cycle for all active NPCs."""
        initiatives: list[dict[str, str]] = []
        for npc in state.present_npcs():
            event = TurnEvent(
                turn=state.turn_number,
                type=event_type,
                description=description_factory(npc),
            )
            memory_store = (
                self.memory_provider.for_npc(state.session_id, npc.entity_id)
                if self.memory_provider is not None
                else None
            )
            self.policy.perceive(npc, event, memory_store)
            intentions = self.policy.reason(
                npc,
                f"Turn {state.turn_number}, day {state.day}, phase {state.world_phase}, "
                f"location {npc.location_id}",
                memory_store,
            )
            if self.policy.should_act(npc, RhythmConfig(), state.turn_number) and intentions:
                best = max(intentions, key=lambda item: item.priority)
                npc.last_action_turn = state.turn_number
                initiatives.append(
                    {
                        "npc_id": npc.entity_id,
                        "action": best.action,
                        "reason": best.reason,
                    }
                )
            await self._process_a2a(npc, state)
        return initiatives

    async def _process_a2a(self, sender: NPCEntity, state: WorldState) -> None:
        """Deliver queued messages and apply communication relationship effects."""
        for message in list(sender.outbox):
            recipient = state.get_npc(message.recipient_id)
            if recipient is not None:
                recipient.inbox.append(message)
            sender.outbox.remove(message)
