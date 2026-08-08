from __future__ import annotations

import asyncio

from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.entities import Player
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import Location, WorldState


class MarkerCompressor:
    def compress(self, state: WorldState, max_tokens: int = 8000) -> str:
        del state, max_tokens
        return "COMPRESSED-SNAPSHOT"


class CapturingLLM:
    def __init__(self) -> None:
        self.snapshot = ""

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        del player_input
        self.snapshot = snapshot
        return CheckProposal(check_type=CheckType.NO_CHECK, description="look")

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        del snapshot, resolved_outcome
        return "Guardi."

    async def clarify(self, snapshot: str, player_input: str) -> str:
        del snapshot
        return player_input

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        del scene_description, world_state
        return {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}


class FakeRenderer:
    def is_available(self) -> bool:
        return False

    async def render(self, visual_contract: JSONObject) -> str:
        del visual_contract
        return "unused"


class FakeStore:
    def __init__(self, state: WorldState) -> None:
        self.state = state

    async def load(self, session_id: str) -> WorldState | None:
        return self.state if session_id == self.state.session_id else None

    async def save(self, session_id: str, state: WorldState) -> None:
        del session_id
        self.state = state

    async def list_sessions(self) -> list[str]:
        return [self.state.session_id]

    async def delete(self, session_id: str) -> None:
        del session_id


class FakeBus:
    async def publish(self, event: object) -> None:
        del event

    def subscribe(self, event_type: str, handler: object) -> None:
        del event_type, handler


def make_state() -> WorldState:
    return WorldState(
        session_id="s1",
        worldpack_id="w1",
        player=Player(
            entity_id="player",
            name="Hero",
            outfit=[],
            stats={},
            inventory=[],
            location_id="beach",
            conditions=[],
            knowledge=[],
        ),
        npcs={},
        locations={"beach": Location(location_id="beach", name="Beach")},
    )


def test_orchestrator_uses_injected_snapshot_compressor() -> None:
    llm = CapturingLLM()
    store = FakeStore(make_state())
    orch = TurnOrchestrator(
        llm,
        FakeRenderer(),
        store,
        FakeBus(),
        snapshot_compressor=MarkerCompressor(),
    )

    asyncio.run(orch.play_turn("s1", "Guardo"))

    assert llm.snapshot == "COMPRESSED-SNAPSHOT"
