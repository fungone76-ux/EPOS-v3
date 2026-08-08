"""Application turn orchestration."""
from __future__ import annotations

import copy
import time

from epos_v3.domain.checks import CheckProposal, CheckType, ResolvedCheck
from epos_v3.domain.events import ImageRendered, SceneCommitted, TurnCompleted, TurnStarted
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState

from .agents import AgentService
from .npc_policy import LongTermMemoryProviderPort
from .outfit_requests import OutfitRequestService
from .npc_summons import apply_explicit_npc_summon
from .checkpoint import CheckpointService
from .commit import CommitService
from .diagnostics import DiagnosticsService
from .initiative_integration import InitiativeIntegrationService
from .initiative_narration import InitiativeNarrationService
from .narration_context import build_narration_snapshot
from .phase_services import Phase1Service, Phase2Service
from .ports import EventBusPort, LLMPort, PlayerDecisionPort, RendererPort, StorePort, VisualCompilerPort, WorldRulesPort, SnapshotCompressorPort
from .validation import ValidationService
from .visual_canonicalizer import canonicalize_vst
from .visual_intent import apply_visual_intent


class TurnOrchestrator:
    """Coordinate a complete turn while keeping Python authoritative."""

    def __init__(
        self,
        llm: LLMPort,
        renderer: RendererPort,
        store: StorePort,
        event_bus: EventBusPort,
        decision_port: PlayerDecisionPort | None = None,
        world_rules: WorldRulesPort | None = None,
        visual_compiler: VisualCompilerPort | None = None,
        memory_provider: LongTermMemoryProviderPort | None = None,
        snapshot_compressor: SnapshotCompressorPort | None = None,
    ) -> None:
        """Create the orchestrator with injected external dependencies."""
        self.llm = llm
        self.renderer = renderer
        self.store = store
        self.event_bus = event_bus
        self.decision_port = decision_port
        self.world_rules = world_rules
        self.visual_compiler = visual_compiler
        self.phase1 = Phase1Service(llm)
        self.phase2 = Phase2Service(llm)
        self.committer = CommitService()
        self.checkpoint = CheckpointService(store)
        self.diagnostics = DiagnosticsService()
        self.validator = ValidationService()
        self.agent_service = AgentService(memory_provider=memory_provider)
        self.snapshot_compressor = snapshot_compressor
        self.initiative_narrator = InitiativeNarrationService(llm)
        self.initiative_integration = InitiativeIntegrationService()
        self.outfit_requests = OutfitRequestService()

    async def play_turn(self, session_id: str, player_input: str) -> dict[str, object]:
        """Execute a new turn from player input through authoritative resolution."""
        start = time.monotonic()
        state = await self.store.load(session_id)
        if state is None:
            raise ValueError(f"Session not found: {session_id}")
        await self.event_bus.publish(
            TurnStarted(
                session_id=session_id,
                turn_number=state.turn_number + 1,
                player_input=player_input,
            )
        )
        snapshot = self._build_snapshot(state)
        try:
            proposal = await self.phase1.run(snapshot, player_input)
        except Exception:
            proposal = await self.phase1.fallback("Phase 1 unavailable")
        state = apply_explicit_npc_summon(state, proposal, player_input)
        valid, errors = self.validator.validate_check_proposal(proposal, state)
        destination_result = self._invalid_destination_result(state, proposal, errors)
        if destination_result is not None:
            return destination_result
        remote_result = self._remote_target_result(state, proposal, errors)
        if remote_result is not None:
            return remote_result
        if not valid:
            try:
                proposal = await self.phase1.revise(snapshot, player_input, errors)
            except Exception:
                proposal = await self.phase1.fallback("Phase 1 validation retry unavailable")
            valid, _ = self.validator.validate_check_proposal(proposal, state)
            if not valid:
                proposal = await self.phase1.fallback("Phase 1 validation fallback")
        choice = await self._get_player_choice(proposal, state)
        resolved = self.committer.resolve_check(proposal, state, choice)
        await self.checkpoint.save(session_id, state, proposal, resolved)
        return await self._continue_from_resolved(
            session_id=session_id,
            state=state,
            proposal=proposal,
            resolved=resolved,
            start=start,
            player_input=player_input,
        )

    async def resume_turn(self, session_id: str) -> dict[str, object]:
        """Resume after a crash from the post-roll checkpoint without rerolling."""
        restored = await self.checkpoint.restore(session_id)
        if restored is None:
            raise ValueError(f"No checkpoint found: {session_id}")
        state, proposal, resolved = restored
        return await self._continue_from_resolved(
            session_id=session_id,
            state=state,
            proposal=proposal,
            resolved=resolved,
            start=time.monotonic(),
            player_input=proposal.description,
        )

    async def _continue_from_resolved(
        self,
        *,
        session_id: str,
        state: WorldState,
        proposal: CheckProposal,
        resolved: ResolvedCheck,
        start: float,
        player_input: str,
    ) -> dict[str, object]:
        """Continue a turn after dice resolution, shared by new and resumed turns."""
        state = self._apply_declared_movement(state, proposal)
        outfit_resolution = self.outfit_requests.resolve(state, proposal, resolved)
        scene_state = state
        if outfit_resolution.mutations:
            scene_state = self.committer.apply_mutations(
                state,
                resolved,
                {"mutations": outfit_resolution.mutations},
            )
        brief_social = self._is_brief_social_input(player_input)
        direct_social = self._is_direct_social_input(player_input, proposal)
        focused_interaction = self._is_focused_interaction_input(player_input, proposal)
        snapshot = self._build_narration_snapshot(
            scene_state,
            proposal,
            player_input=player_input,
            brief_social=brief_social,
            direct_social=direct_social,
            focused_interaction=focused_interaction,
            outfit_resolution=outfit_resolution.model_dump(mode="json"),
        )
        try:
            scene_text = await self.phase2.run(snapshot, resolved)
        except Exception:
            scene_text = "[Narration unavailable]"
        try:
            vst = await self.phase2.generate_vst(scene_text, scene_state)
        except Exception:
            vst = {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}
        vst = canonicalize_vst(vst, scene_state)
        vst = apply_visual_intent(vst, scene_state, proposal, player_input)
        scene_valid, scene_errors = self.validator.validate_scene(vst, scene_state)
        if not scene_valid:
            try:
                scene_text = await self.phase2.revise(snapshot, resolved, scene_errors)
                vst = await self.phase2.generate_vst(scene_text, scene_state)
                vst = canonicalize_vst(vst, scene_state)
                vst = apply_visual_intent(vst, scene_state, proposal, player_input)
            except Exception:
                scene_text = "[Narration unavailable due to validation errors]"
                vst = {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}
            scene_valid, _ = self.validator.validate_scene(vst, scene_state)
            if not scene_valid:
                vst = {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}
        commit_vst = copy.deepcopy(vst)
        llm_mutations = [
            mutation
            for mutation in vst.get("mutations", [])
            if isinstance(mutation, dict)
            and mutation.get("type") not in {"outfit_wear", "outfit_remove"}
        ]
        commit_vst["mutations"] = [*outfit_resolution.mutations, *llm_mutations]
        new_state = self.committer.apply_mutations(state, resolved, commit_vst)
        new_state.turn_number += 1
        available_events: list[dict[str, object]] = []
        if self.world_rules is not None:
            self.world_rules.refresh_state_missions(new_state)
            available_events = self.world_rules.available_state_events(new_state)
        initiatives = await self.agent_service.process_agents(new_state)
        initiatives = [
            await self.initiative_narrator.narrate(new_state, initiative)
            for initiative in initiatives
        ]
        self.initiative_integration.record(new_state, initiatives)
        visible_initiatives = [
            initiative
            for initiative in initiatives
            if (
                (actor := new_state.get_npc(initiative["npc_id"])) is not None
                and actor.location_id == new_state.player.location_id
                and not self._suppress_routine_target_initiative(
                    initiative,
                    proposal,
                    brief_social=(brief_social or direct_social or focused_interaction),
                )
            )
        ]
        scene_text = self.initiative_integration.compose(scene_text, visible_initiatives)
        await self.store.save(session_id, new_state)
        await self.checkpoint.clear(session_id)
        await self.event_bus.publish(
            SceneCommitted(
                session_id=session_id,
                turn_number=new_state.turn_number,
                mutations=commit_vst.get("mutations", []),
            )
        )
        image_path: str | None = None
        visual_contract: JSONObject = {}
        visual_error: str | None = None
        try:
            visual_contract = self._compile_visual(vst, new_state)
        except Exception as exc:
            visual_contract = {}
            visual_error = str(exc)
        if self.renderer.is_available() and visual_contract:
            try:
                image_path = await self.renderer.render(visual_contract)
                await self.event_bus.publish(
                    ImageRendered(
                        session_id=session_id,
                        turn_number=new_state.turn_number,
                        image_path=image_path,
                        prompt_hash="",
                    )
                )
            except Exception:
                image_path = None
        diagnostics = self.diagnostics.collect(state, new_state, proposal, resolved, scene_text)
        duration_ms = int((time.monotonic() - start) * 1000)
        await self.event_bus.publish(
            TurnCompleted(
                session_id=session_id,
                turn_number=new_state.turn_number,
                duration_ms=duration_ms,
            )
        )
        return {
            "turn_number": new_state.turn_number,
            "narration": scene_text,
            "image_path": image_path,
            "visual_prompt": visual_contract.get("prompt"),
            "visual_negative_prompt": visual_contract.get("negative_prompt"),
            "visual_loras": visual_contract.get("loras", []),
            "visual_error": visual_error,
            "outcome": (
                "no_check"
                if proposal.check_type == CheckType.NO_CHECK
                else resolved.outcome.value
            ),
            "initiatives": visible_initiatives,
            "available_events": available_events,
            "diagnostics": diagnostics,
            "duration_ms": duration_ms,
        }

    def _invalid_destination_result(
        self,
        state: WorldState,
        proposal: CheckProposal,
        errors: list[str],
    ) -> dict[str, object] | None:
        """Return a non-consuming clarification for an unknown destination."""
        destination_id = proposal.destination_location_id
        if destination_id is None or f"unknown destination: {destination_id}" not in errors:
            return None
        return {
            "turn_number": state.turn_number,
            "narration": (
                f"Non conosco una destinazione valida chiamata {destination_id!r}. "
                "Scegli una location esistente nel mondo."
            ),
            "image_path": None,
            "outcome": "clarification",
            "initiatives": [],
            "available_events": [],
            "diagnostics": {},
            "duration_ms": 0,
        }

    @staticmethod
    def _apply_declared_movement(
        state: WorldState,
        proposal: CheckProposal,
    ) -> WorldState:
        """Apply validated player movement on a deep copy without advancing time."""
        destination_id = proposal.destination_location_id
        if destination_id is None:
            return state
        if destination_id not in state.locations:
            raise ValueError(f"unknown destination: {destination_id}")
        moved = copy.deepcopy(state)
        moved.player.location_id = destination_id
        return WorldState.model_validate(moved.model_dump(mode="python"))

    def _remote_target_result(
        self,
        state: WorldState,
        proposal: CheckProposal,
        errors: list[str],
    ) -> dict[str, object] | None:
        """Return a non-consuming clarification when a named target is elsewhere."""
        remote_ids = [
            target_id
            for target_id in proposal.target_ids
            if any(
                error == f"target {target_id} not at player location {state.player.location_id}"
                for error in errors
            )
        ]
        if not remote_ids:
            return None
        target_id = remote_ids[0]
        npc = state.get_npc(target_id)
        if npc is None:
            return None
        location = state.locations.get(npc.location_id)
        location_name = location.name if location is not None else npc.location_id
        return {
            "turn_number": state.turn_number,
            "narration": (
                f"{npc.name} non è qui. In questo momento si trova a {location_name}. "
                "Puoi raggiungerla oppure fare qualcos'altro."
            ),
            "image_path": None,
            "outcome": "clarification",
            "initiatives": [],
            "available_events": [],
            "diagnostics": {},
            "duration_ms": 0,
        }

    async def _get_player_choice(self, proposal: CheckProposal, state: WorldState) -> str:
        """Obtain an explicit player decision; no-check needs no decision."""
        if proposal.check_type == CheckType.NO_CHECK:
            return "safe"
        if self.decision_port is None:
            raise RuntimeError("A PlayerDecisionPort is required for checks")
        return await self.decision_port.choose(proposal, state)

    @staticmethod
    def _is_brief_social_input(player_input: str) -> bool:
        """Detect a short greeting/social cue without expanding into a broader request."""
        normalized = " ".join(player_input.lower().replace(",", " ").split())
        words = normalized.split()
        if len(words) > 5:
            return False
        greetings = {"ciao", "salve", "buongiorno", "buonasera", "hey", "ehi"}
        return bool(words) and words[0] in greetings

    @staticmethod
    def _is_direct_social_input(player_input: str, proposal: CheckProposal) -> bool:
        """Detect concise social dialogue that should stay locally focused."""
        normalized = player_input.casefold()
        if any(token in normalized for token in ("vado ", "raggiungo ", "mi sposto", "vai a ")):
            return False
        markers = (
            "?",
            "chiedo",
            "domando",
            "dico",
            "parlo",
            "consigli",
            "saluto",
            "cosa mi",
            "cosa consigli",
        )
        if not any(marker in normalized for marker in markers):
            return False
        return bool(proposal.target_ids) or len(normalized.split()) <= 16

    @staticmethod
    def _is_focused_interaction_input(player_input: str, proposal: CheckProposal) -> bool:
        """Detect a short player-local action focused on a named/targeted NPC."""
        if not proposal.target_ids:
            return False
        normalized = player_input.casefold().strip()
        if not normalized or len(normalized.split()) > 28:
            return False
        if any(token in normalized for token in ("vado ", "raggiungo ", "mi sposto", "vai a ")):
            return False
        markers = (
            "guardo", "guardando", "osservo", "osservando", "noto", "mentre",
            "mi avvicino", "sfioro", "tocco", "indico", "chiamo", "vieni qui",
            "raggiungimi", "fammi vedere", "mostrami",
        )
        return any(marker in normalized for marker in markers)

    @staticmethod
    def _suppress_routine_target_initiative(
        initiative: dict[str, str],
        proposal: CheckProposal,
        *,
        brief_social: bool,
    ) -> bool:
        """Suppress routine goal pursuit when the player just addressed that NPC."""
        if not brief_social:
            return False
        if not initiative.get("reason", "").startswith("Goal non soddisfatto:"):
            return False
        if not proposal.target_ids:
            return True
        return initiative.get("npc_id") in proposal.target_ids

    @staticmethod
    def _build_narration_snapshot(
        state: WorldState,
        proposal: CheckProposal,
        *,
        player_input: str = "",
        brief_social: bool = False,
        direct_social: bool = False,
        focused_interaction: bool = False,
        outfit_resolution: dict[str, object] | None = None,
    ) -> str:
        """Build a player-local narration context with the authoritative action."""
        return build_narration_snapshot(
            state,
            proposal,
            player_input=player_input,
            brief_social=brief_social,
            direct_social=direct_social,
            focused_interaction=focused_interaction,
            outfit_resolution=outfit_resolution,
        )

    def _build_snapshot(self, state: WorldState) -> str:
        """Create a read-only deterministic snapshot for the LLM."""
        if self.snapshot_compressor is not None:
            return self.snapshot_compressor.compress(state)
        return state.model_dump_json()

    def _compile_visual(self, vst: JSONObject, state: WorldState) -> JSONObject:
        """Compile only authoritative VST/state data into a renderer contract."""
        if self.visual_compiler is not None:
            return self.visual_compiler.compile(vst, state)
        return {
            "vst": vst,
            "worldpack_id": state.worldpack_id,
            "turn_number": state.turn_number,
        }
