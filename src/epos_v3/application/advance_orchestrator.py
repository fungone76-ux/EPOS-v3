"""Orchestrate explicit player-controlled world time advancement."""

from __future__ import annotations

from .agents import AgentService
from .initiative_narration import InitiativeNarrationPort, InitiativeNarrationService
from .initiative_integration import InitiativeIntegrationService
from .ports import StorePort, WorldRulesPort
from .time_advance import TimeAdvanceService


class TimeAdvanceOrchestrator:
    """Coordinate one explicit clock advance without involving the LLM."""

    def __init__(
        self,
        store: StorePort,
        world_rules: WorldRulesPort | None = None,
        initiative_llm: InitiativeNarrationPort | None = None,
        agent_service: AgentService | None = None,
    ) -> None:
        """Initialize the explicit time-advance use case.

        Args:
            store: Persistence port for loading and saving the session.
            world_rules: Optional Worldpack-driven mission and event evaluator.
        """
        self.store = store
        self.world_rules = world_rules
        self.clock = TimeAdvanceService()
        self.agents = agent_service or AgentService()
        self.initiative_integration = InitiativeIntegrationService()
        self.initiative_narrator = (
            InitiativeNarrationService(initiative_llm) if initiative_llm is not None else None
        )

    async def advance(self, session_id: str) -> dict[str, object]:
        """Advance exactly one phase after an explicit player request.

        Args:
            session_id: Session to advance.

        Returns:
            A compact result containing the new clock, available events,
            mission state, and autonomous NPC initiatives.

        Raises:
            ValueError: If the session does not exist or the clock is invalid.
        """
        state = await self.store.load(session_id)
        if state is None:
            raise ValueError(f"Session not found: {session_id}")

        advanced = self.clock.advance(state)
        advanced.turn_number += 1

        available_events: list[dict[str, object]] = []
        if self.world_rules is not None:
            self.world_rules.refresh_state_missions(advanced)
            available_events = self.world_rules.available_state_events(advanced)

        initiatives = await self.agents.process_time_advance(advanced)
        if self.initiative_narrator is not None:
            initiatives = [
                await self.initiative_narrator.narrate(advanced, initiative)
                for initiative in initiatives
            ]
        self.initiative_integration.record(advanced, initiatives)
        narration = self.initiative_integration.compose("", initiatives)
        await self.store.save(session_id, advanced)

        return {
            "turn_number": advanced.turn_number,
            "day": advanced.day,
            "phase": advanced.world_phase,
            "available_events": available_events,
            "initiatives": initiatives,
            "narration": narration,
            "pending_missions": list(advanced.pending_missions),
            "completed_missions": list(advanced.completed_missions),
        }
