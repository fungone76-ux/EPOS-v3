"""Generic gameplay rules driven by Worldpack data."""

from __future__ import annotations

from collections.abc import Mapping

from epos_v3.domain.entities import Relationship
from epos_v3.domain.missions import Mission
from epos_v3.domain.world import WorldState

from .models import LoadedWorldpack


class WorldpackGameplay:
    """Evaluate missions and events without world-specific hardcoding."""

    def refresh_missions(self, loaded: LoadedWorldpack) -> None:
        """Refresh mission unlocks, objectives, and terminal states."""
        self.refresh_state_missions(loaded.world)

    def refresh_state_missions(self, state: WorldState) -> None:
        """Refresh missions using rules persisted inside a WorldState."""
        mission_rows = _list_of_mappings(state.gameplay_rules.get("missions", []))
        rows_by_id = {str(row.get("id")): row for row in mission_rows}
        for mission_id, mission in state.missions.items():
            row = rows_by_id.get(mission_id, {})
            if not mission.is_active and not mission.is_completed and not mission.is_failed:
                if self._mission_unlocked_state(state, row):
                    mission.is_active = True
                    if mission.turn_started is None:
                        mission.turn_started = state.turn_number
            required = _string_list(row.get("required_flags", []))
            required_set = set(required)
            for objective in mission.objectives:
                if objective.objective_id in required_set:
                    objective.completed = bool(state.global_flags.get(objective.objective_id, False))
            if (
                row.get("complete_when_required_flags") is True
                and required
                and all(bool(state.global_flags.get(flag, False)) for flag in required)
            ):
                completion_flag = row.get("completion_flag")
                if isinstance(completion_flag, str):
                    state.global_flags[completion_flag] = True
                self._mark_completed_state(state, mission)
                continue
            if _any_true(state.global_flags, _string_list(row.get("terminal_failure_flags", []))):
                self._mark_failed(mission)
            elif _any_true(state.global_flags, _string_list(row.get("terminal_success_flags", []))):
                self._mark_completed_state(state, mission)

    def available_events(
        self,
        loaded: LoadedWorldpack,
        phase: str,
        *,
        player_request: bool = False,
    ) -> list[dict[str, object]]:
        """Return events whose clock, location, and trigger currently match."""
        if _intro_active(loaded.world):
            return []
        result: list[dict[str, object]] = []
        for event in loaded.events.values():
            if not self._clock_matches(loaded, event, phase):
                continue
            location_id = event.get("location_id")
            if isinstance(location_id, str) and loaded.world.player.location_id != location_id:
                continue
            trigger = event.get("trigger", {})
            if isinstance(trigger, Mapping) and not self._trigger_matches(
                loaded, trigger, phase, player_request
            ):
                continue
            result.append(dict(event))
        return result

    def complete_event(self, loaded: LoadedWorldpack, event_id: str) -> None:
        """Mark an event completed and apply its declared completion flag."""
        event = loaded.events.get(event_id)
        if event is None:
            raise ValueError(f"unknown event: {event_id}")
        completion_flag = event.get("completion_flag")
        if isinstance(completion_flag, str):
            loaded.world.global_flags[completion_flag] = True
        loaded.world.global_flags[f"{event_id}_completed"] = True
        self.refresh_missions(loaded)

    def available_state_events(
        self, state: WorldState, *, player_request: bool = False
    ) -> list[dict[str, object]]:
        """Return currently available events from rules persisted in state."""
        if _intro_active(state):
            return []
        result: list[dict[str, object]] = []
        for event in _list_of_mappings(state.gameplay_rules.get("events", [])):
            normalized = {str(key): value for key, value in event.items()}
            if not self._clock_matches_state(state, normalized, state.world_phase):
                continue
            location_id = normalized.get("location_id")
            if isinstance(location_id, str) and state.player.location_id != location_id:
                continue
            trigger = normalized.get("trigger", {})
            if isinstance(trigger, Mapping) and not self._trigger_matches_state(
                state, trigger, state.world_phase, player_request
            ):
                continue
            result.append(normalized)
        return result

    def _mission_unlocked_state(
        self, state: WorldState, row: Mapping[object, object]
    ) -> bool:
        """Return whether a mission's authored unlock rule currently matches."""
        reveal = row.get("reveal")
        if reveal == "initial":
            return True
        condition = row.get("unlock_when")
        return isinstance(condition, Mapping) and self._condition_matches_state(state, condition)

    def _condition_matches_state(
        self, state: WorldState, condition: Mapping[object, object]
    ) -> bool:
        """Evaluate one authored mission unlock condition."""
        event_id = condition.get("event_completed")
        if isinstance(event_id, str):
            return bool(state.global_flags.get(f"{event_id}_completed", False))
        flag = condition.get("flag")
        if isinstance(flag, str):
            return state.global_flags.get(flag) == condition.get("expected", True)
        npc_id = condition.get("relationship")
        field = condition.get("field")
        minimum = condition.get("minimum")
        if isinstance(npc_id, str) and isinstance(field, str) and isinstance(minimum, int):
            relationship = state.player.relationships.get(npc_id, Relationship())
            value = getattr(relationship, field, None)
            return isinstance(value, int) and value >= minimum
        return False

    def _mission_unlocked(self, loaded: LoadedWorldpack, row: Mapping[object, object]) -> bool:
        """Return whether a loaded mission's authored unlock rule matches."""
        reveal = row.get("reveal")
        if reveal == "initial":
            return True
        condition = row.get("unlock_when")
        if not isinstance(condition, Mapping):
            return False
        return self._condition_matches(loaded, condition)

    def _condition_matches(
        self, loaded: LoadedWorldpack, condition: Mapping[object, object]
    ) -> bool:
        """Evaluate a loaded-world mission unlock condition."""
        return self._condition_matches_state(loaded.world, condition)

    def _clock_matches(
        self, loaded: LoadedWorldpack, event: Mapping[str, object], phase: str
    ) -> bool:
        """Return whether an event matches the current day and phase."""
        return self._clock_matches_state(loaded.world, event, phase)

    def _clock_matches_state(
        self, state: WorldState, event: Mapping[str, object], phase: str
    ) -> bool:
        """Return whether an event matches one authoritative state clock."""
        day_range = event.get("day_range")
        if isinstance(day_range, list) and len(day_range) == 2:
            start, end = day_range
            if isinstance(start, int) and isinstance(end, int):
                if not start <= state.day <= end:
                    return False
        phases = event.get("phases")
        if isinstance(phases, list) and phase not in phases:
            return False
        return True

    def _trigger_matches(
        self,
        loaded: LoadedWorldpack,
        trigger: Mapping[object, object],
        phase: str,
        player_request: bool,
    ) -> bool:
        """Evaluate a trigger against a loaded Worldpack."""
        return self._trigger_matches_state(loaded.world, trigger, phase, player_request)

    def _trigger_matches_state(
        self,
        state: WorldState,
        trigger: Mapping[object, object],
        phase: str,
        player_request: bool,
    ) -> bool:
        """Evaluate only trigger forms explicitly supported by the Worldpack schema."""
        flag_missing = trigger.get("flag_missing")
        if isinstance(flag_missing, str):
            return not bool(state.global_flags.get(flag_missing, False))

        mission_id = trigger.get("mission_active")
        if isinstance(mission_id, str):
            mission = state.missions.get(mission_id)
            return bool(mission and mission.is_active and not mission.is_completed and not mission.is_failed)

        flag = trigger.get("flag")
        if isinstance(flag, str):
            return state.global_flags.get(flag) == trigger.get("expected", True)

        if trigger.get("player_request") is True:
            return player_request

        relationship_id = trigger.get("relationship")
        relationship_field = trigger.get("field")
        if not isinstance(relationship_field, str):
            legacy_field = trigger.get("relationship_field")
            relationship_field = legacy_field if isinstance(legacy_field, str) else None
        minimum = trigger.get("minimum")
        if isinstance(relationship_field, str) and isinstance(minimum, int):
            if isinstance(relationship_id, str):
                relationship = state.player.relationships.get(relationship_id, Relationship())
                value = getattr(relationship, relationship_field, None)
                return isinstance(value, int) and value >= minimum
            return any(
                isinstance((value := getattr(relationship, relationship_field, None)), int)
                and value >= minimum
                for relationship in state.player.relationships.values()
            )

        day = trigger.get("day")
        trigger_phase = trigger.get("phase")
        if isinstance(day, int) and state.day != day:
            return False
        if isinstance(trigger_phase, str) and phase != trigger_phase:
            return False
        if isinstance(day, int) or isinstance(trigger_phase, str):
            return True
        return "random_weight" in trigger

    @staticmethod
    def _mark_failed(mission: Mission) -> None:
        """Mark a mission failed without mutating unrelated state."""
        mission.is_failed = True
        mission.is_active = False

    @staticmethod
    def _mark_completed(loaded: LoadedWorldpack, mission: Mission) -> None:
        """Mark a loaded-world mission completed."""
        WorldpackGameplay._mark_completed_state(loaded.world, mission)

    @staticmethod
    def _mark_completed_state(state: WorldState, mission: Mission) -> None:
        """Mark a mission completed in one authoritative WorldState."""
        mission.is_completed = True
        mission.is_active = False
        mission.turn_completed = state.turn_number
        if mission.mission_id not in state.completed_missions:
            state.completed_missions.append(mission.mission_id)


def _intro_active(state: WorldState) -> bool:
    """Return whether an explicitly initialized Worldpack intro is gating freeplay."""
    if bool(state.global_flags.get("resort_intro_completed", False)):
        return False
    return bool(state.global_flags.get("resort_intro_active", False))


def _list_of_mappings(value: object) -> list[Mapping[object, object]]:
    """Return only mapping rows from authored list data."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    """Return only strings from authored list data."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _any_true(flags: Mapping[str, object], names: list[str]) -> bool:
    """Return whether any named authoritative flag is truthy."""
    return any(bool(flags.get(name, False)) for name in names)
