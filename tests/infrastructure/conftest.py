import pytest

from epos_v3.domain.entities import NPCEntity, Player
from epos_v3.domain.outfit import OutfitItem
from epos_v3.domain.world import Location, WorldState


@pytest.fixture
def sample_world() -> WorldState:
    outfit = [OutfitItem(slot="torso", item_id="shirt", name="Shirt")]
    player = Player(
        entity_id="player", name="Player", outfit=outfit, stats={"sarissa": 1}, inventory=[],
        location_id="beach", conditions=[], knowledge=[]
    )
    npc = NPCEntity(
        entity_id="npc", name="Luna", archetype="scout", base_prompt="", negative_prompt="",
        role_prompt="", personality="calm", speech_style="plain", desires=[], fears=[], goals=[],
        secrets=[], red_lines=[], intimate_profile="", stats={"sarissa": 1}, location_id="beach",
        is_present=True, is_alive=True, outfit=outfit, conditions=[], knowledge=[], known_secrets=[],
        false_beliefs=[], discoveries=[]
    )
    location = Location(location_id="beach", name="Beach")
    return WorldState(
        session_id="s1", worldpack_id="default", player=player,
        npcs={"npc": npc}, locations={"beach": location},
    )
