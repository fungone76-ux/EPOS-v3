from pathlib import Path

from epos_v3.domain.entities import Relationship
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader

ROOT = Path(__file__).parents[2] / "worldpacks" / "resort_world"


def _loaded():
    return WorldpackLoader().load(ROOT, session_id="rules-test")


def test_progressive_mission_unlocks_from_relationship() -> None:
    loaded = _loaded()
    loaded.world.player.relationships["stella"] = Relationship(respect=1)

    WorldpackGameplay().refresh_missions(loaded)

    assert loaded.world.missions["mission_stella_promotion"].is_active is True


def test_progressive_mission_unlocks_from_completed_event() -> None:
    loaded = _loaded()
    loaded.world.global_flags["event_bath_for_two_completed"] = True

    WorldpackGameplay().refresh_missions(loaded)

    assert loaded.world.missions["mission_maria_stability"].is_active is True


def test_mission_objectives_and_terminal_success_follow_flags() -> None:
    loaded = _loaded()
    state = loaded.world
    state.global_flags.update({
        "resort_service_assessed": True,
        "bank_debt_disclosed": True,
        "resort_final_decision": True,
        "resort_saved": True,
    })

    WorldpackGameplay().refresh_missions(loaded)

    mission = state.missions["mission_resort_future"]
    assert all(objective.completed for objective in mission.objectives)
    assert mission.is_completed is True
    assert "mission_resort_future" in state.completed_missions


def test_event_is_available_only_at_matching_clock_location_and_trigger() -> None:
    loaded = _loaded()
    loaded.apply_clock(day=1, phase="sera")
    loaded.world.player.location_id = "loc_suite"

    events = WorldpackGameplay().available_events(loaded, phase="sera")

    assert "event_bath_for_two" in {event["id"] for event in events}


def test_completing_event_sets_completion_and_event_flags() -> None:
    loaded = _loaded()

    WorldpackGameplay().complete_event(loaded, "event_bath_for_two")

    assert loaded.world.global_flags["maria_bath_service_recovered"] is True
    assert loaded.world.global_flags["event_bath_for_two_completed"] is True
