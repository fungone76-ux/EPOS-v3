"""Gemini fallback HTTP adapter."""
from __future__ import annotations
import httpx
from epos_v3.application.ports import LLMPort
from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState
from .common import retry_async
from .check_contract import CHECK_PROPOSAL_INSTRUCTIONS
from .narration_contract import NARRATION_INSTRUCTIONS
from .vst_contract import VST_INSTRUCTIONS


class GeminiAdapter(LLMPort):
    """Call Gemini as a secondary LLM provider."""
    def __init__(self, api_key: str, model: str = "gemini-1.5-flash", timeout: int = 120) -> None:
        """Execute the init operation."""
        self.api_key, self.model, self.timeout = api_key, model, timeout
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    async def _generate(self, text: str) -> str:
        """Execute the generate operation."""
        async def operation() -> str:
            """Execute the operation operation."""
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}?key={self.api_key}", json={"system_instruction": {"parts": [{"text": "You are a Game Master. Return valid JSON when requested."}]}, "contents": [{"role": "user", "parts": [{"text": text}]}], "generationConfig": {"temperature": 0.7, "maxOutputTokens": 2048}})
                response.raise_for_status()
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
        return await retry_async(operation, timeout=self.timeout)

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        """Generate and validate a check proposal."""
        import json
        instruction = (
            CHECK_PROPOSAL_INSTRUCTIONS
            + "\nSnapshot:\n"
            + snapshot
            + "\nPlayer: "
            + player_input
        )
        return CheckProposal.model_validate(json.loads(await self._generate(instruction)))

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        """Generate narrative text."""
        import json
        data = json.loads(await self._generate(
            "Return JSON with narration. "
            + NARRATION_INSTRUCTIONS
            + "\nSnapshot:\n"
            + snapshot
            + "\nOutcome: "
            + resolved_outcome
        ))
        return str(data["narration"])

    async def clarify(self, snapshot: str, player_input: str) -> str:
        """Clarify player intent."""
        import json
        data = json.loads(await self._generate(f"Return JSON with clarification.\n{snapshot}\n{player_input}"))
        return str(data["clarification"])

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        """Generate VST JSON."""
        import json
        instruction = (
            VST_INSTRUCTIONS
            + "\nScene:\n"
            + scene_description
            + "\nWorldState:\n"
            + world_state.model_dump_json()
        )
        return json.loads(await self._generate(instruction))
