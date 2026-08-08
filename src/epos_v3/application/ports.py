"""Application ports for external adapters."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.events import DomainEvent
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState


@runtime_checkable
class LLMPort(Protocol):
    """Abstract structured LLM operations used by the application layer."""

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        """Produce a structured check proposal."""
        ...

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        """Narrate an outcome already resolved by Python."""
        ...

    async def clarify(self, snapshot: str, player_input: str) -> str:
        """Clarify ambiguous player intent without changing state."""
        ...

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        """Generate a structured Visual Semantic Table."""
        ...


@runtime_checkable
class VisualCompilerPort(Protocol):
    """Compile validated VST data into a renderer contract."""

    def compile(self, vst: JSONObject, state: WorldState) -> JSONObject:
        """Compile renderer input from authoritative state and VST."""
        ...


@runtime_checkable
class RendererPort(Protocol):
    """Render a compiled visual contract."""

    async def render(self, visual_contract: JSONObject) -> str:
        """Render one visual contract and return its image path."""
        ...

    def is_available(self) -> bool:
        """Return whether this renderer can currently be used."""
        ...


@runtime_checkable
class StorePort(Protocol):
    """Persist and retrieve authoritative game sessions."""

    async def load(self, session_id: str) -> WorldState | None:
        """Load one session if it exists."""
        ...

    async def save(self, session_id: str, state: WorldState) -> None:
        """Persist one authoritative world state."""
        ...

    async def list_sessions(self) -> list[str]:
        """List persisted session identifiers."""
        ...

    async def delete(self, session_id: str) -> None:
        """Delete one persisted session."""
        ...


@runtime_checkable
class EventBusPort(Protocol):
    """Publish domain events without coupling to infrastructure."""

    async def publish(self, event: DomainEvent) -> None:
        """Publish one domain event."""
        ...

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Awaitable[None] | None],
    ) -> None:
        """Register an event handler."""
        ...


@runtime_checkable
class PlayerDecisionPort(Protocol):
    """Obtain an explicit player choice for a proposed check."""

    async def choose(self, proposal: CheckProposal, state: WorldState) -> str:
        """Return the player's selected resolution mode."""
        ...


@runtime_checkable
class WorldRulesPort(Protocol):
    """Evaluate Worldpack-driven mission and event rules."""

    def refresh_state_missions(self, state: WorldState) -> None:
        """Refresh mission state from authoritative world conditions."""
        ...

    def available_state_events(
        self,
        state: WorldState,
        *,
        player_request: bool = False,
    ) -> list[dict[str, object]]:
        """Return events currently available under world conditions."""
        ...


@runtime_checkable
class SnapshotCompressorPort(Protocol):
    """Build an LLM snapshot under a bounded context budget."""

    def compress(self, state: WorldState, max_tokens: int = 8000) -> str:
        """Return a deterministic compressed snapshot."""
        ...
