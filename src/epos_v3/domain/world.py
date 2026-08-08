"""World state and location entities."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .entities import NPCEntity, Player
from .missions import Mission


class TimeOfDay(StrEnum):
    """Canonical world time periods."""

    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NIGHT = "night"


class Location(BaseModel):
    """A world location."""

    model_config = ConfigDict(extra="forbid")
    location_id: str
    name: str
    description: str | None = None
    connected_to: list[str] = Field(default_factory=list)
    properties: dict[str, object] = Field(default_factory=dict)
    items: list[str] = Field(default_factory=list)
    npcs_present: list[str] = Field(default_factory=list)


class WorldState(BaseModel):
    """Complete mutable world snapshot owned by the runtime."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid", arbitrary_types_allowed=True)
    session_id: str
    worldpack_id: str
    turn_number: int = 0
    time_of_day: TimeOfDay = TimeOfDay.MORNING
    day: int = 1
    player: Player
    npcs: dict[str, NPCEntity]
    locations: dict[str, Location]
    missions: dict[str, Mission] = Field(default_factory=dict)
    skill_definitions: dict[str, str] = Field(default_factory=dict)
    global_flags: dict[str, object] = Field(default_factory=dict)
    thread_questions: list[str] = Field(default_factory=list)
    pending_missions: list[str] = Field(default_factory=list)
    completed_missions: list[str] = Field(default_factory=list)
    visual_policy: dict[str, object] = Field(default_factory=dict)
    rendering_config: dict[str, object] = Field(default_factory=dict)
    narrative_policy: dict[str, object] = Field(default_factory=dict)
    gameplay_rules: dict[str, object] = Field(default_factory=dict)
    world_phase: str = "mattina"
    history_digest: str | None = None

    def present_npcs(self) -> list[NPCEntity]:
        """Return living NPCs currently marked present."""
        return [npc for npc in self.npcs.values() if npc.is_alive and npc.is_present]

    def get_npc(self, entity_id: str) -> NPCEntity | None:
        """Return an NPC by canonical entity identifier."""
        return self.npcs.get(entity_id)

    def get_location(self, location_id: str) -> Location | None:
        """Return a location by identifier."""
        return self.locations.get(location_id)
