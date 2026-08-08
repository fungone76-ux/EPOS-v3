import asyncio
from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.domain.entities import Player
from epos_v3.domain.world import Location, WorldState

class BrokenLLM:
    async def propose_check(self, snapshot, player_input): raise TimeoutError("boom")
    async def narrate_scene(self, snapshot, resolved_outcome): raise TimeoutError("boom")
    async def clarify(self, snapshot, player_input): raise TimeoutError("boom")
    async def generate_vst(self, scene_description, world_state): raise TimeoutError("boom")

class Store:
    def __init__(self):
        self.state = WorldState(session_id="s", worldpack_id="w", player=Player(entity_id="player", name="P", outfit=[], stats={}, inventory=[], location_id="l", conditions=[], knowledge=[]), npcs={}, locations={"l": Location(location_id="l", name="L")})
    async def load(self, session_id): return self.state
    async def save(self, session_id, state): self.state = state
    async def list_sessions(self): return ["s"]
    async def delete(self, session_id): pass

class Renderer:
    def is_available(self): return False
    async def render(self, visual_contract): return ""

class Bus:
    async def publish(self, event): pass
    def subscribe(self, event_type, handler): pass

def test_llm_failure_degrades_to_no_check_and_completes():
    orch = TurnOrchestrator(BrokenLLM(), Renderer(), Store(), Bus())
    result = asyncio.run(orch.play_turn("s", "look"))
    assert result["outcome"] == "no_check"
    assert result["turn_number"] == 1
