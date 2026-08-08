from epos_v3.domain.entities import NPCEntity, Relationship, RhythmConfig
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.events import TurnEvent
from epos_v3.infrastructure.agents.npc_agent import NPCPolicy
from epos_v3.infrastructure.visual.vst_generator import VSTGenerator
from epos_v3.infrastructure.visual.prompt_compiler import SemanticPromptCompiler


def make_npc() -> NPCEntity:
    return NPCEntity(
        entity_id="luna", name="Luna", visual_gender="female", archetype="mystic", base_prompt="silver hair",
        negative_prompt="bad anatomy", character_lora=[], role_prompt="mysterious woman",
        personality="calm", speech_style="poetic", desires=[], fears=[], goals=[], secrets=[],
        red_lines=[], intimate_profile="", stats={"Eros": 3, "Sarissa": 1}, location_id="beach",
        is_present=True, is_alive=True, outfit=[OutfitItem(slot="torso", item_id="dress", name="Dress", coverage=0.8)],
        conditions=[], knowledge=[], known_secrets=[], false_beliefs=[], discoveries=[],
        relationships={"player": Relationship(trust=9, attraction=9)},
        emotional_state={"attraction": 9, "joy": 0, "anger": 0, "fear": 0, "trust": 0, "sadness": 0, "melancholy": 0},
    )


def test_agent_perceive_keeps_last_20_and_core_memory() -> None:
    npc = make_npc()
    agent = NPCPolicy()
    for turn in range(1, 23):
        event = TurnEvent(turn=turn, type="scene", description=f"event {turn}", target_id="player", importance=8 if turn == 22 else 3, tags=[])
        agent.perceive(npc, event)
    assert len(npc.short_term_memory) == 20
    assert npc.short_term_memory[-1].text == "event 22"
    assert npc.core_memories[-1].text == "event 22"


def test_agent_should_act_uses_policy_and_rhythm() -> None:
    npc = make_npc()
    agent = NPCPolicy()
    agent.reason(npc, "the player is close")
    assert agent.should_act(npc, RhythmConfig(minimum_turn_gap=3, initiative_threshold=5), 10)
    npc.last_action_turn = 9
    assert not agent.should_act(npc, RhythmConfig(minimum_turn_gap=3, initiative_threshold=5), 10)


def test_mood_mapping_attraction() -> None:
    npc = make_npc()
    subject = {"pose_tags": [], "expression": "", "gaze": ""}
    result = VSTGenerator()._apply_mood_mapping(npc, subject)
    assert result["distance_from_camera"] == "close_up"
    assert result["gaze"] == "looking_at_viewer"
    assert "leaning_forward" in result["pose_tags"]


def test_body_state_from_outfit() -> None:
    npc = make_npc()
    npc.outfit = [OutfitItem(slot="torso", item_id="bra", name="Bra", coverage=0.4)]
    subject = VSTGenerator()._compile_subject(npc)
    assert subject["body_state"] == "bottomless"


def test_vst_compiler_output_and_counting_tags() -> None:
    npc = make_npc()
    vst = VSTGenerator().generate("Luna watches the sea", "turn_0001", "beach", [npc], None)
    result = SemanticPromptCompiler().compile(vst, {"luna": {"base_prompt": "silver hair", "negative_prompt": "extra arms"}})
    assert "1girl" not in result["prompt"]
    assert "silver hair" in result["prompt"]
    assert "facial_expressions" in result["negative_prompt"]
    assert "extra arms" in result["negative_prompt"]


def test_vst_schema_is_structured() -> None:
    npc = make_npc()
    vst = VSTGenerator().generate("A discovery", "turn_0002", "beach", [npc], None)
    assert set(vst) == {"scene_id", "location", "subjects", "action", "visual_focus", "camera", "lighting", "style", "safety"}
    assert vst["safety"]["outfit_authoritative"] is True


def test_generic_visual_outfit_is_never_interpreted_as_nudity() -> None:
    from epos_v3.domain.entities import NPCEntity
    from epos_v3.domain.outfit import OutfitItem

    npc = NPCEntity(
        entity_id="npc_generic",
        name="Generic",
        archetype="guest",
        base_prompt="portrait",
        negative_prompt="",
        character_lora=[],
        role_prompt="guest",
        personality="",
        speech_style="",
        desires=[],
        fears=[],
        goals=[],
        secrets=[],
        red_lines=[],
        intimate_profile="",
        stats={},
        location_id="lobby",
        is_present=True,
        is_alive=True,
        outfit=[OutfitItem(slot="visual", item_id="dress", name="evening dress", coverage=1.0, layer=0)],
        conditions=[],
        knowledge=[],
        known_secrets=[],
        false_beliefs=[],
        discoveries=[],
    )

    subject = VSTGenerator()._compile_subject(npc)

    assert subject["body_state"] == "clothed"
