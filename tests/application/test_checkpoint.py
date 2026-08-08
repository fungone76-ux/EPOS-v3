import asyncio
from pathlib import Path

from epos_v3.application.checkpoint import CheckpointService
from epos_v3.domain.checks import CheckProposal, CheckType, ResolvedCheck
from epos_v3.domain.dice import DiceResult
from epos_v3.domain.entities import Player
from epos_v3.domain.world import Location, WorldState


class DummyStore:
    async def load(self, session_id: str):
        return None
    async def save(self, session_id: str, state):
        return None
    async def list_sessions(self):
        return []
    async def delete(self, session_id: str):
        return None


def state() -> WorldState:
    return WorldState(
        session_id="s1", worldpack_id="w1",
        player=Player(entity_id="player", name="Hero", outfit=[], stats={}, inventory=[], location_id="beach", conditions=[], knowledge=[]),
        npcs={}, locations={"beach": Location(location_id="beach", name="Beach")},
    )


def test_checkpoint_save_and_resume(tmp_path: Path) -> None:
    service = CheckpointService(DummyStore(), tmp_path)
    proposal = CheckProposal(check_type=CheckType.NO_CHECK, description="test")
    resolved = ResolvedCheck(proposal=proposal, pool_size=0, dice=DiceResult([]), choice="roll")
    asyncio.run(service.save("test", state(), proposal, resolved))
    checkpoint = asyncio.run(service.resume("test"))
    assert checkpoint is not None
    assert checkpoint["turn_number"] == 0
    assert checkpoint["resolved"]["outcome"] == "failure"
    assert not (tmp_path / "test" / "checkpoint.json.tmp").exists()
