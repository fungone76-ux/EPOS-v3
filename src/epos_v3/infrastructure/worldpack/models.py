"""Validated Worldpack source models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import TimeOfDay, WorldState


class WorldpackFile(BaseModel):
    """Common metadata present in every Worldpack YAML file."""

    model_config = ConfigDict(extra="allow")
    schema_version: int
    world_id: str


class ScheduleConfig(BaseModel):
    """NPC schedules indexed by day and phase."""

    model_config = ConfigDict(extra="allow")
    phases: list[str]
    schedules: dict[str, dict[int, dict[str, str]]]


class WardrobeConfig(BaseModel):
    """NPC outfits indexed by day and phase."""

    model_config = ConfigDict(extra="allow")
    wardrobes: dict[str, dict[int, dict[str, list[str]]]]


class LoadedWorldpack(BaseModel):
    """Runtime bundle containing the domain state and canonical source data."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    world: WorldState
    schedules: ScheduleConfig
    wardrobes: WardrobeConfig
    events: dict[str, dict[str, object]] = Field(default_factory=dict)
    source_data: dict[str, dict[str, object]] = Field(default_factory=dict)

    def apply_clock(self, day: int, phase: str) -> None:
        """Apply a canonical clock position to NPC locations and outfits."""
        if day < 1:
            raise ValueError("day must be >= 1")
        if phase not in self.schedules.phases:
            raise ValueError(f"unknown phase: {phase}")
        self.world.day = day
        self.world.time_of_day = _phase_to_time_of_day(phase)
        self.world.world_phase = phase
        for npc_id, npc in self.world.npcs.items():
            location = self.schedules.schedules.get(npc_id, {}).get(day, {}).get(phase)
            if location is None:
                npc.is_present = False
                continue
            npc.location_id = location
            npc.is_present = True
            outfit = self.wardrobes.wardrobes.get(npc_id, {}).get(day, {}).get(phase)
            if outfit is not None:
                npc.outfit = _outfit_items(outfit)
        _refresh_location_presence(self.world)


def _phase_to_time_of_day(phase: str) -> TimeOfDay:
    """Map a Worldpack phase to the canonical domain time enum."""
    mapping = {
        "mattina": TimeOfDay.MORNING,
        "pomeriggio": TimeOfDay.AFTERNOON,
        "sera": TimeOfDay.EVENING,
        "notte": TimeOfDay.NIGHT,
    }
    if phase not in mapping:
        raise ValueError(f"unknown phase: {phase}")
    return mapping[phase]


def _outfit_items(names: list[str]) -> list[OutfitItem]:
    """Convert authored outfit names into authoritative runtime items."""
    return [
        OutfitItem(slot="visual", item_id=f"item_{index}", name=name, coverage=1.0, layer=index)
        for index, name in enumerate(names)
    ]


def _refresh_location_presence(world: WorldState) -> None:
    """Rebuild each location's presence list from the authoritative NPC state."""
    for location in world.locations.values():
        location.npcs_present = []
    for npc in world.npcs.values():
        if npc.is_present and npc.is_alive and npc.location_id in world.locations:
            world.locations[npc.location_id].npcs_present.append(npc.entity_id)
