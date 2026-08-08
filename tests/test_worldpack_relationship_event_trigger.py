"""Regression tests for relationship-gated Worldpack events."""

from types import SimpleNamespace

from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay


def _state(jealousy: int) -> SimpleNamespace:
    return SimpleNamespace(
        player=SimpleNamespace(
            relationships={"stella": SimpleNamespace(jealousy=jealousy)}
        ),
        global_flags={},
        missions={},
        day=3,
    )


def test_relationship_trigger_opens_when_threshold_is_met() -> None:
    """A Worldpack event may be gated by one authoritative relationship field."""
    trigger = {"relationship": "stella", "field": "jealousy", "minimum": 2}

    assert WorldpackGameplay()._trigger_matches_state(  # noqa: SLF001
        _state(2), trigger, "sera", False
    )


def test_relationship_trigger_stays_closed_below_threshold() -> None:
    """The same event stays unavailable while the threshold is unmet."""
    trigger = {"relationship": "stella", "field": "jealousy", "minimum": 2}

    assert not WorldpackGameplay()._trigger_matches_state(  # noqa: SLF001
        _state(1), trigger, "sera", False
    )
