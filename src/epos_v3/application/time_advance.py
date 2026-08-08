"""Player-controlled world clock advancement."""

from __future__ import annotations

import copy
from collections.abc import Mapping

from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import TimeOfDay, WorldState


class TimeAdvanceService:
    """Advance the world clock only on an explicit player request."""

    def advance(self, state: WorldState) -> WorldState:
        """Return a validated copy advanced by exactly one configured phase.

        Args:
            state: Current authoritative world state. It is never mutated.

        Returns:
            A deep-copied state at the next configured phase.

        Raises:
            ValueError: If clock configuration or current phase is invalid.
        """
        clock = state.gameplay_rules.get("clock")
        if not isinstance(clock, Mapping):
            raise ValueError("missing clock configuration")
        phases_raw = clock.get("phases")
        if not isinstance(phases_raw, list) or not phases_raw or not all(
            isinstance(item, str) for item in phases_raw
        ):
            raise ValueError("clock phases must be a non-empty string list")
        phases = list(phases_raw)
        if state.world_phase not in phases:
            raise ValueError(f"current phase is not configured: {state.world_phase}")

        new_state = copy.deepcopy(state)
        current_index = phases.index(state.world_phase)
        if current_index + 1 < len(phases):
            next_day = state.day
            next_phase = phases[current_index + 1]
        else:
            next_day = state.day + 1
            next_phase = phases[0]

        self._apply_clock(new_state, next_day, next_phase, clock)
        return WorldState.model_validate(new_state.model_dump(mode="python"))

    def _apply_clock(
        self,
        state: WorldState,
        day: int,
        phase: str,
        clock: Mapping[object, object],
    ) -> None:
        """Apply one resolved day/phase to NPC schedule and wardrobe data."""
        schedules = clock.get("schedules", {})
        wardrobes = clock.get("wardrobes", {})
        if not isinstance(schedules, Mapping) or not isinstance(wardrobes, Mapping):
            raise ValueError("invalid clock schedule configuration")

        state.day = day
        state.world_phase = phase
        state.time_of_day = _phase_to_time_of_day(phase)

        for npc_id, npc in state.npcs.items():
            location_id = _nested_day_phase_value(
                schedules, npc_id, day, phase, open_end=bool(clock.get("open_end", False))
            )
            if not isinstance(location_id, str):
                npc.is_present = False
                continue
            if location_id not in state.locations:
                raise ValueError(f"schedule references unknown location: {location_id}")
            npc.location_id = location_id
            npc.is_present = True

            outfit = _nested_day_phase_value(
                wardrobes, npc_id, day, phase, open_end=bool(clock.get("open_end", False))
            )
            if isinstance(outfit, list) and all(isinstance(item, str) for item in outfit):
                npc.outfit = [
                    OutfitItem(
                        slot="visual",
                        item_id=f"item_{index}",
                        name=name,
                        coverage=1.0,
                        layer=index,
                    )
                    for index, name in enumerate(outfit)
                ]

        for location in state.locations.values():
            location.npcs_present = []
        for npc in state.npcs.values():
            if npc.is_alive and npc.is_present and npc.location_id in state.locations:
                state.locations[npc.location_id].npcs_present.append(npc.entity_id)


def _nested_day_phase_value(
    root: Mapping[object, object],
    npc_id: str,
    day: int,
    phase: str,
    *,
    open_end: bool = False,
) -> object | None:
    """Execute the nested day phase value operation."""
    npc_rows = root.get(npc_id)
    if not isinstance(npc_rows, Mapping):
        return None
    day_rows = npc_rows.get(day)
    if day_rows is None:
        day_rows = npc_rows.get(str(day))
    if not isinstance(day_rows, Mapping) and open_end:
        authored_days: list[int] = []
        for key in npc_rows:
            if isinstance(key, int):
                authored_days.append(key)
            elif isinstance(key, str) and key.isdigit():
                authored_days.append(int(key))
        eligible = [authored_day for authored_day in authored_days if authored_day <= day]
        if eligible:
            fallback_day = max(eligible)
            day_rows = npc_rows.get(fallback_day)
            if day_rows is None:
                day_rows = npc_rows.get(str(fallback_day))
    if not isinstance(day_rows, Mapping):
        return None
    return day_rows.get(phase)


def _phase_to_time_of_day(phase: str) -> TimeOfDay:
    """Execute the phase to time of day operation."""
    mapping = {
        "mattina": TimeOfDay.MORNING,
        "pomeriggio": TimeOfDay.AFTERNOON,
        "sera": TimeOfDay.EVENING,
        "notte": TimeOfDay.NIGHT,
    }
    try:
        return mapping[phase]
    except KeyError as exc:
        raise ValueError(f"phase has no canonical TimeOfDay mapping: {phase}") from exc
