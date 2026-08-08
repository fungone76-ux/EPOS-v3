from epos_v3.domain.entities import Player
from epos_v3.domain.outfit import OutfitItem

def create_test_player() -> Player:
    return Player(entity_id="player", name="Hero", outfit=[], stats={}, inventory=[], location_id="beach", conditions=[], knowledge=[])

def test_coverage_calculation() -> None:
    player = create_test_player()
    player.outfit = [
        OutfitItem(slot="torso", item_id="shirt", name="Shirt", coverage=0.5),
        OutfitItem(slot="torso", item_id="vest", name="Vest", coverage=0.5),
    ]
    assert player.get_coverage_by_slot("torso") == 0.75

def test_naked_detection() -> None:
    player = create_test_player()
    player.outfit = []
    assert player.is_naked() is True
