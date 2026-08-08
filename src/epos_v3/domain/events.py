"""Domain events and lightweight observed turn events."""

from __future__ import annotations

from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class DomainEvent(BaseModel):
    """Base event published by the domain."""

    model_config = ConfigDict(extra="forbid")
    event_type: str
    session_id: str
    turn_number: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, JsonValue] = Field(default_factory=dict)


class TurnEvent(BaseModel):
    """Event perceived by an NPC, including optional agent metadata."""

    turn: int
    type: str
    description: str
    tags: list[str] = Field(default_factory=list)
    importance: int = Field(default=5, ge=1, le=10)
    emotion: str | None = None
    intensity: int = Field(default=1, ge=1, le=10)
    target_id: str | None = None
    relationship_delta: dict[str, int] | None = None


class TurnStarted(DomainEvent):
    """Turn lifecycle start event."""

    event_type: str = "turn_started"
    player_input: str


class CheckProposed(DomainEvent):
    """Check proposal lifecycle event."""

    event_type: str = "check_proposed"
    check_type: str
    difficulty: int
    pool_size: int


class DiceRolled(DomainEvent):
    """Authoritative dice resolution event."""

    event_type: str = "dice_rolled"
    pool: list[int]
    successes: int
    outcome_level: str


class SceneCommitted(DomainEvent):
    """Atomic scene commit event."""

    event_type: str = "scene_committed"
    mutations: list[dict[str, JsonValue]]


class ImageRendered(DomainEvent):
    """Successful rendering event."""

    event_type: str = "image_rendered"
    image_path: str
    prompt_hash: str


class TurnCompleted(DomainEvent):
    """Turn lifecycle completion event."""

    event_type: str = "turn_completed"
    duration_ms: int


class NPCInitiative(DomainEvent):
    """Autonomous NPC initiative event."""

    event_type: str = "npc_initiative"
    npc_id: str
    action: str
    reason: str


class DisclosureEvent(DomainEvent):
    """Secret disclosure event."""

    event_type: str = "disclosure"
    npc_id: str
    secret_id: str
    disclosed: bool
    truthful: bool
