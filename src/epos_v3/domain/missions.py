"""Mission domain entities."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MissionObjective(BaseModel):
    """A mission objective."""

    model_config = ConfigDict(extra="forbid")
    objective_id: str
    description: str
    completed: bool = False


class MissionTransition(BaseModel):
    """A state transition for a mission."""

    model_config = ConfigDict(extra="forbid")
    from_state: str
    to_state: str
    condition: str


class Mission(BaseModel):
    """A quest-like mission with explicit lifecycle state."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    mission_id: str
    title: str
    description: str | None = None
    prerequisites: list[str] = []
    objectives: list[MissionObjective] = []
    transitions: list[MissionTransition] = []
    rewards: dict[str, object] = {}
    is_active: bool = False
    is_completed: bool = False
    is_failed: bool = False
    turn_started: int | None = None
    turn_completed: int | None = None
