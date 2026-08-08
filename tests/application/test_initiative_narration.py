from __future__ import annotations

import pytest

from epos_v3.application.initiative_narration import InitiativeNarrationService
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader
from pathlib import Path

WORLD = Path(__file__).parents[2] / "worldpacks" / "resort_world"


class FakeLLM:
    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        assert 'victoria' in snapshot
        assert 'fuggire' in snapshot
        assert resolved_outcome == 'npc_initiative'
        return "Victoria arretra di un passo, osservando nervosamente la stanza."


@pytest.mark.asyncio
async def test_narration_wraps_authoritative_npc_action_without_changing_it() -> None:
    state = WorldpackLoader().load(WORLD, session_id="narrative").world
    service = InitiativeNarrationService(FakeLLM())
    initiative = {"npc_id": "victoria", "action": "fuggire", "reason": "Paura (9)"}

    result = await service.narrate(state, initiative)

    assert result["npc_id"] == "victoria"
    assert result["action"] == "fuggire"
    assert result["reason"] == "Paura (9)"
    assert "Victoria" in result["narration"]


@pytest.mark.asyncio
async def test_narration_has_deterministic_fallback_when_llm_fails() -> None:
    class BrokenLLM:
        async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
            raise RuntimeError("offline")

    state = WorldpackLoader().load(WORLD, session_id="fallback").world
    service = InitiativeNarrationService(BrokenLLM())

    result = await service.narrate(
        state,
        {"npc_id": "victoria", "action": "confrontare", "reason": "Rabbia alta"},
    )

    assert result["action"] == "confrontare"
    assert result["narration"] == "Victoria Hale prende l'iniziativa: confrontare."


@pytest.mark.asyncio
async def test_initiative_prompt_forbids_invented_groups_and_player_actions() -> None:
    state = WorldpackLoader().load(WORLD, session_id="initiative-prompt").world

    class CaptureLLM:
        def __init__(self) -> None:
            self.snapshot = ""

        async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
            self.snapshot = snapshot
            return "Actor osserva la sala."

    llm = CaptureLLM()
    service = InitiativeNarrationService(llm)
    await service.narrate(
        state,
        {"npc_id": "actor", "action": "osservare", "reason": "curiosita"},
    )

    assert "Do not invent groups, companions" in llm.snapshot
    assert "Never choose, imply, or narrate a player action" in llm.snapshot


@pytest.mark.asyncio
async def test_initiative_prompt_contains_turn_number_for_cache_separation() -> None:
    state = WorldpackLoader().load(WORLD, session_id="initiative-turn-cache").world
    state.turn_number = 7

    class CaptureLLM:
        def __init__(self) -> None:
            self.snapshot = ""

        async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
            self.snapshot = snapshot
            return "Luna osserva."

    llm = CaptureLLM()
    service = InitiativeNarrationService(llm)
    await service.narrate(
        state,
        {"npc_id": "luna", "action": "osservare", "reason": "curiosita"},
    )

    assert '"turn_number": 7' in llm.snapshot
