import pytest
from epos_v3.domain.identifiers import EntityID

def test_valid_entity_id() -> None:
    eid = EntityID("Hero_1")
    assert eid.value == "hero_1"

def test_invalid_entity_id() -> None:
    with pytest.raises(ValueError):
        EntityID("123bad")
