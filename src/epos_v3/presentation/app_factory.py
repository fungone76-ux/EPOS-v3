"""Dependency composition for the default local runtime."""
from __future__ import annotations

import inspect
import os
from collections.abc import Awaitable, Callable

from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.application.ports import EventBusPort, LLMPort, PlayerDecisionPort, StorePort
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.events import DomainEvent
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState
from epos_v3.infrastructure.llm.cache import CachedLLM
from epos_v3.infrastructure.llm.fallback import FallbackLLM
from epos_v3.infrastructure.llm.gemini_adapter import GeminiAdapter
from epos_v3.infrastructure.llm.openai_adapter import OpenAIAdapter
from epos_v3.infrastructure.context.compression import SnapshotCompressor
from epos_v3.infrastructure.memory.provider import (
    ChromaLongTermMemoryProvider,
    InMemoryLongTermMemoryProvider,
)
from epos_v3.infrastructure.rendering.comfyui import ComfyUIAdapter
from epos_v3.infrastructure.rendering.sd_webui import StableDiffusionWebUIAdapter
from epos_v3.infrastructure.visual.world_compiler import WorldVisualCompiler
from epos_v3.infrastructure.worldpack.gameplay import WorldpackGameplay

EventHandler = Callable[[DomainEvent], object | Awaitable[object]]


class InMemoryEventBus(EventBusPort):
    """Minimal async event bus for local execution."""

    def __init__(self) -> None:
        """Execute the init operation."""
        self.handlers: dict[str, list[EventHandler]] = {}

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all handlers registered for its class name."""
        for handler in self.handlers.get(type(event).__name__, []):
            result = handler(event)
            if inspect.isawaitable(result):
                await result

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register one event handler."""
        self.handlers.setdefault(event_type, []).append(handler)


class LocalLLMStub(LLMPort):
    """Safe offline adapter used when no provider credentials are configured."""

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        """Return a no-check proposal without inventing rules."""
        del snapshot
        return CheckProposal(check_type=CheckType.NO_CHECK, description=player_input)

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        """Return a minimal offline narration."""
        del snapshot, resolved_outcome
        return "L'azione del giocatore viene registrata nel mondo."

    async def clarify(self, snapshot: str, player_input: str) -> str:
        """Echo the input when no LLM is available."""
        del snapshot
        return player_input

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        """Return a minimal offline VST payload."""
        return {
            "scene_id": f"turn-{world_state.turn_number}",
            "location": {"location_id": world_state.player.location_id},
            "subjects": [],
            "action": {"type": "transition", "description": scene_description},
            "mutations": [],
            "dialogue": [],
            "visual": {},
        }


class SafeDecisionPort(PlayerDecisionPort):
    """Offline decision adapter that is never used for no-check proposals."""

    async def choose(self, proposal: CheckProposal, state: WorldState) -> str:
        """Choose the conservative branch for non-interactive runtimes."""
        del proposal, state
        return "safe"


class UnavailableRenderer:
    """Renderer used when ComfyUI is not configured."""

    def is_available(self) -> bool:
        """Report that rendering is unavailable."""
        return False

    async def render(self, visual_contract: JSONObject) -> str:
        """Reject render attempts in offline mode."""
        del visual_contract
        raise RuntimeError("No renderer configured")


def _build_llm() -> LLMPort:
    """Build a configured provider chain, falling back to the offline stub."""
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    primary: LLMPort | None = None
    secondary: LLMPort | None = None
    if openai_key:
        primary = OpenAIAdapter(
            api_key=openai_key,
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )
    if gemini_key:
        gemini = GeminiAdapter(
            api_key=gemini_key,
            model=os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
        )
        if primary is None:
            primary = gemini
        else:
            secondary = gemini

    if primary is None:
        return LocalLLMStub()
    configured: LLMPort = FallbackLLM(primary, secondary) if secondary is not None else primary
    return CachedLLM(configured, db_path=os.getenv("EPOS_LLM_CACHE_DB", "./data/llm_cache.db"))


def _build_renderer() -> ComfyUIAdapter | StableDiffusionWebUIAdapter | UnavailableRenderer:
    """Build the configured local image renderer."""
    renderer = os.getenv(
        "EPOS_RENDER_MODE",
        os.getenv("EPOS_RENDERER", "comfyui"),
    ).strip().lower()
    image_dir = os.getenv("EPOS_IMAGE_DIR", "./data/images")

    if renderer in {"sd_webui", "a1111", "automatic1111", "forge"}:
        endpoint = os.getenv(
            "A1111_BASE_URL",
            os.getenv("EPOS_SD_WEBUI_ENDPOINT", "http://127.0.0.1:7860"),
        ).strip()
        if not endpoint:
            return UnavailableRenderer()
        timeout = int(
            os.getenv(
                "EPOS_A1111_TIMEOUT_SECONDS",
                os.getenv("A1111_TIMEOUT_SECONDS", "600"),
            )
        )
        return StableDiffusionWebUIAdapter(
            endpoint=endpoint,
            timeout=timeout,
            image_dir=image_dir,
            width=int(os.getenv("EPOS_A1111_WIDTH", os.getenv("EPOS_SD_WIDTH", "896"))),
            height=int(os.getenv("EPOS_A1111_HEIGHT", os.getenv("EPOS_SD_HEIGHT", "1152"))),
            steps=int(os.getenv("EPOS_A1111_STEPS", "24")),
            cfg_scale=float(os.getenv("EPOS_A1111_CFG", "7.0")),
            sampler_name=os.getenv("EPOS_A1111_SAMPLER", "DPM++ 2M Karras"),
        )

    endpoint = os.getenv("EPOS_COMFYUI_ENDPOINT", "").strip()
    if not endpoint:
        return UnavailableRenderer()
    ws_endpoint = os.getenv("EPOS_COMFYUI_WS_ENDPOINT", "").strip()
    if not ws_endpoint:
        ws_endpoint = (
            endpoint.replace("https://", "wss://")
            .replace("http://", "ws://")
            .rstrip("/")
            + "/ws"
        )
    return ComfyUIAdapter(
        endpoint=endpoint,
        ws_endpoint=ws_endpoint,
        image_dir=image_dir,
        worldpack_root=os.getenv("EPOS_WORLDPACK_ROOT", "./worldpacks"),
    )

def _build_memory_provider() -> InMemoryLongTermMemoryProvider | ChromaLongTermMemoryProvider:
    """Build the configured NPC long-term memory provider."""
    backend = os.getenv("EPOS_MEMORY_BACKEND", "simple").strip().lower()
    if backend == "chroma":
        return ChromaLongTermMemoryProvider(os.getenv("EPOS_CHROMA_PATH", "./data/chroma"))
    return InMemoryLongTermMemoryProvider()


def create_default_orchestrator(store: StorePort) -> TurnOrchestrator:
    """Create a configuration-aware orchestrator with safe offline degradation."""
    return TurnOrchestrator(
        llm=_build_llm(),
        renderer=_build_renderer(),
        store=store,
        event_bus=InMemoryEventBus(),
        decision_port=SafeDecisionPort(),
        world_rules=WorldpackGameplay(),
        visual_compiler=WorldVisualCompiler(),
        memory_provider=_build_memory_provider(),
        snapshot_compressor=SnapshotCompressor(),
    )
