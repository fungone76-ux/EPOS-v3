"""LLM-facing turn phase services."""
from __future__ import annotations
import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar
from epos_v3.domain.checks import CheckProposal, ResolvedCheck, CheckType
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState
from .ports import LLMPort
from .outfit_request_intent import sanitize_outfit_requests

_TIMEOUT_SECONDS = 120.0
_MAX_ATTEMPTS = 3
_T = TypeVar("_T")

async def _with_retries(operation: Callable[[], Awaitable[_T]]) -> _T:
    """Execute one async operation with bounded timeout, retry, and backoff."""
    last_error: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return await asyncio.wait_for(operation(), timeout=_TIMEOUT_SECONDS)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < _MAX_ATTEMPTS:
                await asyncio.sleep(0.25 * (2 ** attempt))
    assert last_error is not None
    raise last_error

class Phase1Service:
    """Request and revise the authoritative phase-one proposal."""
    def __init__(self, llm: LLMPort) -> None:
        """Execute the init operation."""
        self._llm = llm

    async def run(self, snapshot: str, player_input: str) -> CheckProposal:
        """Ask the LLM for a structured check proposal."""
        proposal = await _with_retries(lambda: self._llm.propose_check(snapshot, player_input))
        return sanitize_outfit_requests(proposal, player_input)

    async def revise(self, snapshot: str, player_input: str, errors: list[str]) -> CheckProposal:
        """Ask the LLM to revise an invalid proposal."""
        feedback = player_input + "\nValidation errors: " + "; ".join(errors)
        proposal = await _with_retries(lambda: self._llm.propose_check(snapshot, feedback))
        return sanitize_outfit_requests(proposal, player_input)

    async def fallback(self, description: str = "Fallback") -> CheckProposal:
        """Return a safe no-check proposal after exhausted LLM recovery."""
        return CheckProposal(check_type=CheckType.NO_CHECK, description=description)

class Phase2Service:
    """Request narration only after Python resolves the outcome."""
    def __init__(self, llm: LLMPort) -> None:
        """Execute the init operation."""
        self._llm = llm

    async def run(self, snapshot: str, resolved: ResolvedCheck) -> str:
        """Narrate an already-resolved outcome."""
        outcome = "no_check" if resolved.proposal.check_type == CheckType.NO_CHECK else resolved.outcome.value
        return await _with_retries(lambda: self._llm.narrate_scene(snapshot, outcome))

    async def generate_vst(self, scene_text: str, state: WorldState) -> JSONObject:
        """Generate a VST through the same timeout/retry policy as other LLM calls."""
        return await _with_retries(lambda: self._llm.generate_vst(scene_text, state))

    async def revise(self, snapshot: str, resolved: ResolvedCheck, errors: list[str]) -> str:
        """Retry narration with validation feedback."""
        outcome = "no_check" if resolved.proposal.check_type == CheckType.NO_CHECK else resolved.outcome.value
        feedback = outcome + "\nValidation errors: " + "; ".join(errors)
        return await _with_retries(lambda: self._llm.narrate_scene(snapshot, feedback))
