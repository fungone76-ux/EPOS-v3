import asyncio
from pathlib import Path

from epos_v3.application.checkpoint import CheckpointService
from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.domain.checks import CheckProposal, CheckType, ResolvedCheck
from epos_v3.domain.dice import DiceResult
from epos_v3.domain.entities import Player
from epos_v3.domain.events import DomainEvent
from epos_v3.domain.world import Location, WorldState


class CountingLLM:
    def __init__(self) -> None:
        self.proposal_calls = 0
        self.narration_calls = 0

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        self.proposal_calls += 1
        raise AssertionError("Phase 1 must not run during checkpoint resume")

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        self.narration_calls += 1
        return f"Ripresa con esito {resolved_outcome}."

    async def clarify(self, snapshot: str, player_input: str) -> str:
        return player_input

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> dict[str, object]:
        return {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}


class MemoryStore:
    def __init__(self) -> None:
        self.saved: WorldState | None = None

    async def load(self, session_id: str) -> WorldState | None:
        return self.saved

    async def save(self, session_id: str, state: WorldState) -> None:
        self.saved = state

    async def list_sessions(self) -> list[str]:
        return [] if self.saved is None else [self.saved.session_id]

    async def delete(self, session_id: str) -> None:
        self.saved = None


class Renderer:
    def is_available(self) -> bool:
        return False

    async def render(self, visual_contract: dict[str, object]) -> str:
        raise AssertionError("Renderer is unavailable")


class Bus:
    async def publish(self, event: DomainEvent) -> None:
        return None

    def subscribe(self, event_type: str, handler: object) -> None:
        return None


def _state() -> WorldState:
    return WorldState(
        session_id="resume",
        worldpack_id="test",
        player=Player(
            entity_id="player",
            name="Player",
            outfit=[],
            stats={"carisma": 2},
            inventory=[],
            location_id="lobby",
            conditions=[],
            knowledge=[],
        ),
        npcs={},
        locations={"lobby": Location(location_id="lobby", name="Lobby")},
        skill_definitions={"carisma": "Persuasione sociale"},
    )


def test_resume_turn_uses_saved_dice_without_phase1_or_reroll(tmp_path: Path) -> None:
    state = _state()
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="Convincere qualcuno",
        skill="carisma",
        difficulty=4,
    )
    saved_dice = DiceResult([6, 2, 5], threshold=4)
    resolved = ResolvedCheck(
        proposal=proposal,
        pool_size=3,
        dice=saved_dice,
        choice="roll",
    )
    store = MemoryStore()
    llm = CountingLLM()
    orchestrator = TurnOrchestrator(llm, Renderer(), store, Bus())
    orchestrator.checkpoint = CheckpointService(store, tmp_path)
    asyncio.run(orchestrator.checkpoint.save("resume", state, proposal, resolved))

    result = asyncio.run(orchestrator.resume_turn("resume"))

    assert llm.proposal_calls == 0
    assert llm.narration_calls == 1
    assert result["outcome"] == "full_success"
    assert result["turn_number"] == 1
    assert result["diagnostics"]["dice_pool"] == [6, 2, 5]
    assert store.saved is not None
    assert store.saved.turn_number == 1


def test_resume_turn_without_checkpoint_is_explicit_error(tmp_path: Path) -> None:
    store = MemoryStore()
    orchestrator = TurnOrchestrator(CountingLLM(), Renderer(), store, Bus())
    orchestrator.checkpoint = CheckpointService(store, tmp_path)

    try:
        asyncio.run(orchestrator.resume_turn("missing"))
    except ValueError as exc:
        assert str(exc) == "No checkpoint found: missing"
    else:
        raise AssertionError("Expected ValueError")
