"""OpenAI HTTP adapter."""
from __future__ import annotations
import httpx
from epos_v3.application.ports import LLMPort
from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState
from .common import json_content, retry_async
from .check_contract import CHECK_PROPOSAL_INSTRUCTIONS
from .narration_contract import NARRATION_INSTRUCTIONS
from .vst_contract import VST_INSTRUCTIONS


class OpenAIAdapter(LLMPort):
    """Call OpenAI using JSON responses and bounded retries."""
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", timeout: int = 120) -> None:
        """Execute the init operation."""
        self.api_key, self.model, self.timeout = api_key, model, timeout

    async def _post(self, messages: list[dict[str, str]]) -> dict[str, object]:
        """Execute the post operation."""
        async def operation() -> dict[str, object]:
            """Execute the operation operation."""
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={"model": self.model, "messages": messages, "response_format": {"type": "json_object"}},
                )
                response.raise_for_status()
                return json_content(response.json())
        return await retry_async(operation, timeout=self.timeout)

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        """Ask the model for a check proposal."""
        data = await self._post([
            {
                "role": "system",
                "content": (
                    "You are a Game Master for an Italian RPG. Return JSON only.\n"
                    + CHECK_PROPOSAL_INSTRUCTIONS
                ),
            },
            {"role": "user", "content": f"Snapshot:\n{snapshot}\nPlayer: {player_input}"},
        ])
        return CheckProposal.model_validate(data)

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        """Ask the model for narrative text."""
        data = await self._post([
            {
                "role": "system",
                "content": (
                    "Write an Italian RPG scene and return JSON {\"narration\": string}. "
                    + NARRATION_INSTRUCTIONS
                ),
            },
            {"role": "user", "content": f"Snapshot:\n{snapshot}\nOutcome: {resolved_outcome}"},
        ])
        narration = data.get("narration")
        if not isinstance(narration, str):
            raise ValueError("Missing narration")
        return narration

    async def clarify(self, snapshot: str, player_input: str) -> str:
        """Ask for a clarification."""
        data = await self._post([{"role": "system", "content": "Clarify the player's intent in Italian. Return JSON {\"clarification\": string}."}, {"role": "user", "content": f"{snapshot}\n{player_input}"}])
        value = data.get("clarification")
        if not isinstance(value, str):
            raise ValueError("Missing clarification")
        return value

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        """Generate a structured VST, never a free-form image prompt."""
        data = await self._post([
            {
                "role": "system",
                "content": "Generate structured visual semantics only.\n" + VST_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": f"Scene:\n{scene_description}\nWorldState:\n{world_state.model_dump_json()}",
            },
        ])
        return data
