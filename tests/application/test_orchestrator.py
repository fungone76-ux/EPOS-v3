import asyncio

from epos_v3.application.orchestrator import TurnOrchestrator
from epos_v3.domain.checks import CheckProposal, CheckType
from epos_v3.domain.entities import Player
from epos_v3.domain.world import Location, WorldState


class FakeLLM:
    async def propose_check(self, snapshot: str, player_input: str):
        return CheckProposal(check_type=CheckType.NO_CHECK, description="look")
    async def narrate_scene(self, snapshot: str, resolved_outcome: str):
        return "Guardi intorno."
    async def clarify(self, snapshot: str, player_input: str):
        return ""
    async def generate_vst(self, scene_description: str, world_state: WorldState):
        return {"mutations": [], "dialogue": [], "subjects": [], "visual": {}}


class FakeRenderer:
    def is_available(self) -> bool:
        return False
    async def render(self, visual_contract: dict) -> str:
        return "unused"


class FakeStore:
    def __init__(self, state: WorldState):
        self.states = {state.session_id: state}
    async def load(self, session_id: str):
        return self.states.get(session_id)
    async def save(self, session_id: str, state: WorldState):
        self.states[session_id] = state
    async def list_sessions(self):
        return list(self.states)
    async def delete(self, session_id: str):
        self.states.pop(session_id, None)


class FakeBus:
    def __init__(self):
        self.events = []
    async def publish(self, event):
        self.events.append(event)
    def subscribe(self, event_type, handler):
        return None


def make_state() -> WorldState:
    return WorldState(
        session_id="s1", worldpack_id="w1",
        player=Player(entity_id="player", name="Hero", outfit=[], stats={}, inventory=[], location_id="beach", conditions=[], knowledge=[]),
        npcs={}, locations={"beach": Location(location_id="beach", name="Beach")},
    )


def test_turn_orchestrator_no_check() -> None:
    store = FakeStore(make_state())
    orch = TurnOrchestrator(FakeLLM(), FakeRenderer(), store, FakeBus())
    result = asyncio.run(orch.play_turn("s1", "Guardo intorno"))
    assert result["turn_number"] == 1
    assert result["outcome"] == "no_check"
    assert store.states["s1"].turn_number == 1


def test_orchestrator_uses_injected_visual_compiler_before_render() -> None:
    class AvailableRenderer:
        def __init__(self) -> None:
            self.contract = None

        def is_available(self) -> bool:
            return True

        async def render(self, visual_contract: dict) -> str:
            self.contract = visual_contract
            return "image.png"

    class Compiler:
        def compile(self, vst: dict, state: WorldState) -> dict:
            return {"compiled": True, "turn_number": state.turn_number}

    store = FakeStore(make_state())
    renderer = AvailableRenderer()
    orch = TurnOrchestrator(
        FakeLLM(),
        renderer,
        store,
        FakeBus(),
        visual_compiler=Compiler(),
    )

    result = asyncio.run(orch.play_turn("s1", "Guardo intorno"))

    assert result["image_path"] == "image.png"
    assert renderer.contract == {"compiled": True, "turn_number": 1}


def test_orchestrator_reports_remote_target_without_consuming_turn() -> None:
    from epos_v3.domain.entities import NPCEntity

    class RemoteTargetLLM(FakeLLM):
        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="observe Luna",
                target_ids=["luna"],
            )

    world = make_state()
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={}, location_id="office",
        is_present=True, is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    store = FakeStore(world)
    orch = TurnOrchestrator(RemoteTargetLLM(), FakeRenderer(), store, FakeBus())

    result = asyncio.run(orch.play_turn("s1", "Guardo Luna"))

    assert result["outcome"] == "clarification"
    assert "Luna" in result["narration"]
    assert "office" in result["narration"]
    assert store.states["s1"].turn_number == 0


def test_orchestrator_moves_player_to_valid_destination_before_narration() -> None:
    from epos_v3.domain.entities import NPCEntity

    class MovementLLM(FakeLLM):
        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Raggiungo Luna alla spiaggia privata.",
                target_ids=["luna"],
                destination_location_id="private_beach",
            )

        async def narrate_scene(self, snapshot: str, resolved_outcome: str):
            assert '"location_id":"private_beach"' in snapshot
            return "Raggiungi la spiaggia privata e trovi Luna."

    world = make_state()
    world.locations["private_beach"] = Location(
        location_id="private_beach", name="Spiaggia privata"
    )
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="",
        negative_prompt="", role_prompt="", personality="calm", speech_style="plain",
        desires=[], fears=[], goals=[], secrets=[], red_lines=[], intimate_profile="",
        stats={}, location_id="private_beach", is_present=True, is_alive=True, outfit=[],
        conditions=[], knowledge=[], known_secrets=[], false_beliefs=[], discoveries=[],
    )
    store = FakeStore(world)
    orch = TurnOrchestrator(MovementLLM(), FakeRenderer(), store, FakeBus())

    result = asyncio.run(
        orch.play_turn("s1", "Vado alla spiaggia privata per raggiungere Luna")
    )

    assert result["outcome"] == "no_check"
    assert store.states["s1"].player.location_id == "private_beach"
    assert store.states["s1"].turn_number == 1
    assert "trovi Luna" in result["narration"]


def test_orchestrator_rejects_unknown_movement_destination_without_consuming_turn() -> None:
    class BadMovementLLM(FakeLLM):
        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Vado in un posto inventato.",
                destination_location_id="not_real",
            )

    store = FakeStore(make_state())
    orch = TurnOrchestrator(BadMovementLLM(), FakeRenderer(), store, FakeBus())

    result = asyncio.run(orch.play_turn("s1", "Vado in un posto inventato"))

    assert result["outcome"] == "clarification"
    assert store.states["s1"].player.location_id == "beach"
    assert store.states["s1"].turn_number == 0


def test_narration_snapshot_is_player_local_and_contains_authoritative_action() -> None:
    from epos_v3.domain.entities import NPCEntity

    class CapturingLLM(FakeLLM):
        def __init__(self) -> None:
            self.narration_snapshot = ""

        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Raggiungo Luna alla spiaggia privata.",
                target_ids=["luna"],
                destination_location_id="private_beach",
            )

        async def narrate_scene(self, snapshot: str, resolved_outcome: str):
            self.narration_snapshot = snapshot
            return "Raggiungi Luna."

    world = make_state()
    world.locations["private_beach"] = Location(location_id="private_beach", name="Spiaggia privata")
    world.locations["office"] = Location(location_id="office", name="Ufficio")
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={}, location_id="private_beach",
        is_present=True, is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    world.npcs["victoria"] = NPCEntity(
        entity_id="victoria", name="Victoria", archetype="manager", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={}, location_id="office",
        is_present=True, is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    store = FakeStore(world)
    llm = CapturingLLM()
    orch = TurnOrchestrator(llm, FakeRenderer(), store, FakeBus())

    asyncio.run(orch.play_turn("s1", "Vado da Luna"))

    assert "Raggiungo Luna alla spiaggia privata." in llm.narration_snapshot
    assert "Luna" in llm.narration_snapshot
    assert "Victoria" not in llm.narration_snapshot


def test_turn_exposes_compiled_visual_prompt_even_when_renderer_unavailable() -> None:
    class Compiler:
        def compile(self, vst: dict, state: WorldState) -> dict:
            return {
                "prompt": "Luna on the private beach, feet clearly visible",
                "negative_prompt": "cropped feet",
                "loras": [{"name": "luna.safetensors", "weight": 0.8}],
                "worldpack_id": state.worldpack_id,
            }

    store = FakeStore(make_state())
    orch = TurnOrchestrator(
        FakeLLM(),
        FakeRenderer(),
        store,
        FakeBus(),
        visual_compiler=Compiler(),
    )

    result = asyncio.run(orch.play_turn("s1", "Guardo Luna"))

    assert result["visual_prompt"] == "Luna on the private beach, feet clearly visible"
    assert result["visual_negative_prompt"] == "cropped feet"
    assert result["visual_loras"] == [{"name": "luna.safetensors", "weight": 0.8}]


def test_short_greeting_requests_brief_social_narration() -> None:
    class GreetingLLM(FakeLLM):
        def __init__(self) -> None:
            self.snapshot = ""

        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Saluto Victoria.",
                target_ids=[],
            )

        async def narrate_scene(self, snapshot: str, resolved_outcome: str):
            self.snapshot = snapshot
            return 'Victoria sorride. "Per divertirti un po'" "', prova il lounge bar."'

    store = FakeStore(make_state())
    llm = GreetingLLM()
    orch = TurnOrchestrator(llm, FakeRenderer(), store, FakeBus())

    asyncio.run(orch.play_turn("s1", "ciao Victoria"))

    assert '"narration_mode":"brief_social"' in llm.snapshot
    assert '"max_sentences":2' in llm.snapshot
    assert "omit environment and outfit exposition" in llm.snapshot.lower()


def test_brief_social_suppresses_routine_target_goal_initiative() -> None:
    from epos_v3.domain.entities import NPCEntity

    class GreetingLLM(FakeLLM):
        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Saluto Victoria.",
                target_ids=["victoria"],
            )

        async def narrate_scene(self, snapshot: str, resolved_outcome: str):
            if resolved_outcome == "npc_initiative":
                return "Victoria parte con un lungo discorso di affari."
            return 'Victoria ricambia il saluto. "Buongiorno. Come posso aiutarti?"'

    world = make_state()
    world.npcs["victoria"] = NPCEntity(
        entity_id="victoria", name="Victoria", archetype="manager", base_prompt="",
        negative_prompt="", role_prompt="", personality="decisa", speech_style="formale",
        desires=[], fears=[], goals=["convincere_player_a_investire"], secrets=[],
        red_lines=[], intimate_profile="", stats={}, location_id="beach", is_present=True,
        is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    store = FakeStore(world)
    orch = TurnOrchestrator(GreetingLLM(), FakeRenderer(), store, FakeBus())

    result = asyncio.run(orch.play_turn("s1", "ciao Victoria"))

    assert "lungo discorso" not in result["narration"]
    assert "ricambia il saluto" in result["narration"]


def test_brief_social_classifier_is_conservative() -> None:
    assert TurnOrchestrator._is_brief_social_input("ciao Victoria")
    assert TurnOrchestrator._is_brief_social_input("Buongiorno, Luna")
    assert not TurnOrchestrator._is_brief_social_input(
        "Ciao Victoria, vorrei discutere nei dettagli dell'acquisto del resort"
    )


def test_turn_exposes_visual_compile_error_instead_of_silently_hiding_it() -> None:
    class BrokenCompiler:
        def compile(self, vst: dict, state: WorldState) -> dict:
            raise ValueError("invalid VST camera")

    store = FakeStore(make_state())
    orch = TurnOrchestrator(
        FakeLLM(),
        FakeRenderer(),
        store,
        FakeBus(),
        visual_compiler=BrokenCompiler(),
    )

    result = asyncio.run(orch.play_turn("s1", "Guardo intorno"))

    assert result["visual_prompt"] is None
    assert result["visual_error"] == "invalid VST camera"


def test_direct_social_snapshot_requests_concise_reply() -> None:
    class DialogueLLM(FakeLLM):
        def __init__(self) -> None:
            self.snapshot = ""

        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Chiedo a Victoria cosa consiglia.",
                target_ids=["victoria"],
            )

        async def narrate_scene(self, snapshot: str, resolved_outcome: str):
            self.snapshot = snapshot
            return 'Victoria sorride. "Per divertirti un po'" "', prova il lounge bar."'

    store = FakeStore(make_state())
    llm = DialogueLLM()
    orch = TurnOrchestrator(llm, FakeRenderer(), store, FakeBus())

    asyncio.run(orch.play_turn("s1", "cosa mi consigli per divertirmi un po?"))

    assert '"narration_mode":"direct_social"' in llm.snapshot
    assert '"max_sentences":2' in llm.snapshot

def test_direct_social_snapshot_preserves_raw_player_input() -> None:
    snapshot = TurnOrchestrator._build_narration_snapshot(
        make_state(),
        CheckProposal(check_type=CheckType.NO_CHECK, description="Parlo"),
        player_input="le dico guardandole le gambe",
        direct_social=True,
    )

    assert '"raw_player_input":"le dico guardandole le gambe"' in snapshot


def test_direct_social_without_target_suppresses_routine_goal_initiative() -> None:
    initiative = {
        "npc_id": "victoria",
        "action": "Convincere il player a investire",
        "reason": "Goal non soddisfatto: investire",
        "narration": "Victoria parla di investimento.",
    }
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Rispondo alla conversazione",
        target_ids=[],
    )

    assert TurnOrchestrator._suppress_routine_target_initiative(
        initiative,
        proposal,
        brief_social=True,
    )


def test_successful_outfit_request_is_committed_and_exposed_to_narration() -> None:
    import time

    from epos_v3.domain.checks import OutfitRequest, ResolvedCheck
    from epos_v3.domain.dice import DiceResult
    from epos_v3.domain.entities import NPCEntity
    from epos_v3.domain.outfit import OutfitItem

    class OutfitLLM(FakeLLM):
        def __init__(self) -> None:
            self.snapshot = ""

        async def narrate_scene(self, snapshot: str, resolved_outcome: str):
            self.snapshot = snapshot
            return 'Victoria annuisce. "Va bene."'

        async def generate_vst(self, scene_description: str, world_state: WorldState):
            return {
                "mutations": [],
                "dialogue": [],
                "subjects": [{"entity_id": "victoria"}],
                "visual": {},
            }

    state = make_state()
    state.skill_definitions = {"negoziazione": ""}
    state.player.stats["negoziazione"] = 3
    state.npcs["victoria"] = NPCEntity(
        entity_id="victoria",
        name="Victoria Hale",
        archetype="manager",
        base_prompt="",
        negative_prompt="",
        role_prompt="",
        personality="",
        speech_style="",
        desires=[],
        fears=[],
        goals=[],
        secrets=[],
        red_lines=[],
        intimate_profile="",
        stats={},
        location_id="beach",
        is_present=True,
        is_alive=True,
        outfit=[
            OutfitItem(slot="visual", item_id="dress", name="ivory bodycon blazer mini dress", coverage=1.0, layer=0),
            OutfitItem(slot="visual", item_id="shoes", name="nude stiletto pumps", coverage=1.0, layer=1),
        ],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
    )
    state.gameplay_rules["clock"] = {
        "wardrobes": {
            "victoria": {1: {"mattina": ["ivory bodycon blazer mini dress", "nude stiletto pumps", "sheer black stockings"]}}
        },
        "outfit_aliases": {
            "victoria": {
                "pantyhose neri": "sheer black stockings",
                "senza scarpe": "@footwear",
            }
        },
    }
    proposal = CheckProposal(
        check_type=CheckType.CHECK_PROPOSAL,
        description="Chiedo a Victoria di indossare pantyhose neri senza scarpe.",
        skill="negoziazione",
        difficulty=1,
        target_ids=["victoria"],
        stakes={
            "full_success": "accepted",
            "partial_success": "accepted with reservation",
            "failure": "refused",
            "critical_failure": "refused",
        },
        outfit_requests=[
            OutfitRequest(
                target_id="victoria",
                wear_terms=["pantyhose neri"],
                remove_terms=["senza scarpe"],
            )
        ],
    )
    resolved = ResolvedCheck(
        proposal=proposal,
        pool_size=2,
        dice=DiceResult([6, 6], 1),
        choice="roll",
    )
    store = FakeStore(state)
    llm = OutfitLLM()
    orch = TurnOrchestrator(llm, FakeRenderer(), store, FakeBus())

    result = asyncio.run(
        orch._continue_from_resolved(
            session_id="s1",
            state=state,
            proposal=proposal,
            resolved=resolved,
            start=time.monotonic(),
            player_input="indossa i pantyhose neri senza scarpe",
        )
    )

    names = [item.name for item in store.states["s1"].npcs["victoria"].outfit]
    assert "sheer black stockings" in names
    assert "nude stiletto pumps" not in names
    assert '"accepted":true' in llm.snapshot
    assert result["turn_number"] == 1


def test_orchestrator_explicit_call_moves_remote_npc_to_player() -> None:
    from epos_v3.domain.entities import NPCEntity

    class CallLLM(FakeLLM):
        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Chiamo Luna perché venga qui.",
                target_ids=["luna"],
            )

        async def narrate_scene(self, snapshot: str, resolved_outcome: str):
            assert '"location_id":"beach"' in snapshot
            assert '"entity_id":"luna"' in snapshot
            return "Luna arriva. \"Eccomi, mi hai chiamata?\""

    world = make_state()
    world.locations["office"] = Location(location_id="office", name="Office")
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={}, location_id="office",
        is_present=True, is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    world.locations["office"].npcs_present = ["luna"]
    store = FakeStore(world)
    orch = TurnOrchestrator(CallLLM(), FakeRenderer(), store, FakeBus())

    result = asyncio.run(orch.play_turn("s1", "Luna, puoi venire qui?"))

    assert result["outcome"] == "no_check"
    assert "Eccomi" in result["narration"]
    assert store.states["s1"].npcs["luna"].location_id == "beach"
    assert "luna" in store.states["s1"].locations["beach"].npcs_present
    assert "luna" not in store.states["s1"].locations["office"].npcs_present
    assert store.states["s1"].turn_number == 1


def test_orchestrator_remote_mention_does_not_summon_npc() -> None:
    from epos_v3.domain.entities import NPCEntity

    class MentionLLM(FakeLLM):
        async def propose_check(self, snapshot: str, player_input: str):
            return CheckProposal(
                check_type=CheckType.NO_CHECK,
                description="Penso a Luna.",
                target_ids=["luna"],
            )

    world = make_state()
    world.locations["office"] = Location(location_id="office", name="Office")
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="scout", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={}, location_id="office",
        is_present=True, is_alive=True, outfit=[], conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[],
    )
    store = FakeStore(world)
    orch = TurnOrchestrator(MentionLLM(), FakeRenderer(), store, FakeBus())

    result = asyncio.run(orch.play_turn("s1", "Chissà cosa sta facendo Luna"))

    assert result["outcome"] == "clarification"
    assert store.states["s1"].npcs["luna"].location_id == "office"
    assert store.states["s1"].turn_number == 0


def test_focused_npc_observation_uses_concise_narration_mode() -> None:
    from epos_v3.domain.entities import NPCEntity

    world = make_state()
    world.npcs["luna"] = NPCEntity(
        entity_id="luna", name="Luna", archetype="companion", base_prompt="", negative_prompt="",
        role_prompt="", personality="observant", speech_style="brief", desires=[], fears=[],
        goals=["Riconoscere il legame con il gruppo del protagonista"], secrets=[], red_lines=[],
        intimate_profile="", stats={}, location_id="beach", is_present=True, is_alive=True,
        outfit=[], conditions=[], knowledge=[], known_secrets=[], false_beliefs=[], discoveries=[],
    )
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Il giocatore osserva Luna mentre si allena.",
        target_ids=["luna"],
    )

    assert TurnOrchestrator._is_focused_interaction_input(
        "guardo il suo culo mentre si allena sulla spiaggia", proposal
    )
    snapshot = TurnOrchestrator._build_narration_snapshot(
        world,
        proposal,
        player_input="guardo il suo culo mentre si allena sulla spiaggia",
        focused_interaction=True,
    )

    assert '"narration_mode":"focused_interaction"' in snapshot
    assert '"max_sentences":2' in snapshot
    assert "Riconoscere il legame" not in snapshot
    assert '"goals"' not in snapshot
    assert '"intentions"' not in snapshot


def test_focused_npc_observation_suppresses_routine_goal_initiative() -> None:
    proposal = CheckProposal(
        check_type=CheckType.NO_CHECK,
        description="Osservo Luna",
        target_ids=["luna"],
    )
    initiative = {
        "npc_id": "luna",
        "reason": "Goal non soddisfatto: qualcosa di privato",
        "action": "approach",
        "narration": "Luna si avvicina.",
    }

    assert TurnOrchestrator._suppress_routine_target_initiative(
        initiative,
        proposal,
        brief_social=True,
    )
