import asyncio
from pathlib import Path

from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader


WORLD = Path(__file__).resolve().parents[2] / "worldpacks" / "resort_world"


class CarismaLLM:
    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        assert '"carisma"' in snapshot
        return CheckProposal(
            check_type=CheckType.CHECK_PROPOSAL,
            description="Convincere il personale",
            skill="carisma",
            difficulty=4,
            target_ids=[],
            opposition="none",
            stakes={
                "full_success": "convinto",
                "partial_success": "incerto",
                "failure": "rifiuta",
                "critical_failure": "si offende",
            },
        )

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        return "La conversazione procede."

    async def clarify(self, snapshot: str, player_input: str) -> str:
        return ""

    async def generate_vst(self, scene_description: str, world_state):
        return {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}


class Decision:
    async def choose(self, proposal, state) -> str:
        return "roll"


class Renderer:
    def is_available(self) -> bool:
        return False

    async def render(self, visual_contract: dict) -> str:
        return "unused"


class Store:
    def __init__(self, state):
        self.state = state

    async def load(self, session_id: str):
        return self.state if self.state.session_id == session_id else None

    async def save(self, session_id: str, state):
        self.state = state

    async def list_sessions(self):
        return [self.state.session_id]

    async def delete(self, session_id: str):
        return None


class Bus:
    async def publish(self, event):
        return None

    def subscribe(self, event_type, handler):
        return None


def test_real_worldpack_skill_reaches_authoritative_dice_pool() -> None:
    state = WorldpackLoader().load(WORLD, session_id="dynamic-e2e").world
    store = Store(state)
    orchestrator = TurnOrchestrator(
        CarismaLLM(), Renderer(), store, Bus(), decision_port=Decision()
    )

    result = asyncio.run(orchestrator.play_turn("dynamic-e2e", "Provo a convincerli"))

    # Azure Crown player carisma=3, so Python must roll 1 base + 3 rating.
    assert result["diagnostics"]["pool_size"] == 4
    assert result["turn_number"] == 1
