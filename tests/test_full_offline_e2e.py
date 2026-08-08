from __future__ import annotations

import asyncio
from pathlib import Path

from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.application.ports import RendererPort
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState
from epos_v3.infrastructure.persistence.json_store import JsonStore
from epos_v3.infrastructure.rendering.workflow_template import ComfyWorkflowTemplate
from epos_v3.infrastructure.visual.world_compiler import WorldVisualCompiler
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay
from epos_v3.infrastructure.worldpack.loader import WorldpackLoader
from epos_v3.presentation.app_factory import InMemoryEventBus, SafeDecisionPort

WORLD = Path(__file__).parents[1] / "worldpacks" / "resort_world"


class EndToEndLLM:
    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        del snapshot, player_input
        return CheckProposal(check_type=CheckType.NO_CHECK, description="look around")

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        del snapshot, resolved_outcome
        return "Osservi la lobby dell'Azure Crown."

    async def clarify(self, snapshot: str, player_input: str) -> str:
        del snapshot
        return player_input

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        del scene_description
        present = [
            npc for npc in world_state.present_npcs()
            if npc.location_id == world_state.player.location_id
        ]
        subjects: list[JSONObject] = [
            {
                "entity_id": npc.entity_id,
                "gender": npc.visual_gender,
                "pose_tags": ["standing"],
                "expression": "neutral",
                "gaze": "toward_player",
                "outfit_visible": [],
                "body_state": "clothed",
                "skin_visible": [],
            }
            for npc in present
        ]
        return {
            "style": {
                "art_style": "runtime-placeholder",
                "color_palette": "warm",
                "mood": "arrival",
                "rendering": "detailed",
                "lora": [],
                "model": "worldpack",
            },
            "location": {
                "location_id": world_state.player.location_id,
                "time_of_day": world_state.world_phase,
                "lighting": "natural",
                "environment_tags": ["resort"],
            },
            "subjects": subjects,
            "action": {"description": "arrival", "interaction": "conversation"},
            "camera": {
                "shot_type": "medium_shot",
                "angle": "eye_level",
                "orientation": "front",
                "depth_of_field": "deep",
                "background_blur": False,
            },
            "lighting": {"primary": "soft", "rim_light": ""},
            "mutations": [],
            "dialogue": [],
            "visual": {},
        }


class WorkflowRenderer(RendererPort):
    def __init__(self) -> None:
        self.workflow: JSONObject | None = None

    def is_available(self) -> bool:
        return True

    async def render(self, visual_contract: JSONObject) -> str:
        workflow_file = visual_contract.get("workflow_file")
        assert isinstance(workflow_file, str)
        self.workflow = ComfyWorkflowTemplate(WORLD / workflow_file).build(visual_contract)
        return "offline://rendered-image"


def test_full_worldpack_turn_visual_workflow_and_persistence(tmp_path: Path) -> None:
    state = WorldpackLoader().load(WORLD, session_id="e2e").world
    store = JsonStore(tmp_path / "sessions")
    asyncio.run(store.save("e2e", state))
    renderer = WorkflowRenderer()
    orchestrator = TurnOrchestrator(
        llm=EndToEndLLM(),
        renderer=renderer,
        store=store,
        event_bus=InMemoryEventBus(),
        decision_port=SafeDecisionPort(),
        world_rules=WorldpackGameplay(),
        visual_compiler=WorldVisualCompiler(),
    )

    result = asyncio.run(orchestrator.play_turn("e2e", "Guardo intorno"))
    saved = asyncio.run(store.load("e2e"))

    assert result["turn_number"] == 1
    assert result["outcome"] == "no_check"
    assert result["image_path"] == "offline://rendered-image"
    assert saved is not None and saved.turn_number == 1
    assert renderer.workflow is not None
    assert renderer.workflow["2"]["inputs"]["text"] != "RUNTIME_POSITIVE_PROMPT"
    assert renderer.workflow["1"]["inputs"]["ckpt_name"] == "luna_main_model.safetensors"
