from copy import deepcopy

import pytest

from epos_v3.application.time_advance import TimeAdvanceService
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


WORLD = __import__('pathlib').Path(__file__).parents[2] / 'worldpacks' / 'resort_world'


def test_advance_moves_exactly_one_phase() -> None:
    state = WorldpackLoader().load(WORLD, session_id='clock').world

    advanced = TimeAdvanceService().advance(state)

    assert state.day == 1
    assert state.world_phase == 'mattina'
    assert advanced.day == 1
    assert advanced.world_phase == 'pomeriggio'


def test_advance_rolls_to_next_day_after_last_phase() -> None:
    loaded = WorldpackLoader().load(WORLD, session_id='clock')
    loaded.apply_clock(day=1, phase='notte')

    advanced = TimeAdvanceService().advance(loaded.world)

    assert advanced.day == 2
    assert advanced.world_phase == 'mattina'


def test_advance_updates_npc_schedule_and_wardrobe() -> None:
    state = WorldpackLoader().load(WORLD, session_id='clock').world

    advanced = TimeAdvanceService().advance(state)

    assert advanced.npcs['victoria'].location_id == 'loc_victoria_office'
    assert advanced.npcs['victoria'].outfit[0].name == 'black ultra fitted blazer dress'
    assert 'victoria' in advanced.locations['loc_victoria_office'].npcs_present


def test_advance_is_atomic_and_does_not_mutate_input_on_failure() -> None:
    state = WorldpackLoader().load(WORLD, session_id='clock').world
    before = deepcopy(state)
    state.gameplay_rules['clock'] = {'phases': []}

    with pytest.raises(ValueError, match='clock phases'):
        TimeAdvanceService().advance(state)

    # Aside from the deliberate bad config inserted by the test, runtime fields stay untouched.
    assert state.day == before.day
    assert state.world_phase == before.world_phase
    assert state.npcs == before.npcs


def test_open_end_uses_last_defined_day_as_schedule_fallback() -> None:
    loaded = WorldpackLoader().load(WORLD, session_id='clock-open-end')
    loaded.apply_clock(day=7, phase='notte')

    advanced = TimeAdvanceService().advance(loaded.world)

    assert advanced.day == 8
    assert advanced.world_phase == 'mattina'
    expected = loaded.schedules.schedules['victoria'][7]['mattina']
    assert advanced.npcs['victoria'].location_id == expected
    assert advanced.npcs['victoria'].is_present is True


def test_open_end_fallback_keeps_real_runtime_day() -> None:
    loaded = WorldpackLoader().load(WORLD, session_id='clock-open-end')
    loaded.apply_clock(day=7, phase='notte')

    current = TimeAdvanceService().advance(loaded.world)
    for _ in range(3):
        current = TimeAdvanceService().advance(current)
    day9 = TimeAdvanceService().advance(current)

    assert day9.day == 9
    assert day9.world_phase == 'mattina'
