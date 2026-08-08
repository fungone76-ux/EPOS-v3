import json
from pathlib import Path

import pytest

from epos_v3.domain.checks import CheckProposal
from epos_v3.infrastructure.llm.cache import CachedLLM
from epos_v3.infrastructure.persistence.json_store import JsonStore
from epos_v3.infrastructure.rendering.image_cache import ImageCache


class FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        self.calls += 1
        return CheckProposal(skill="sarissa", difficulty=3, description="test")

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        self.calls += 1
        return "narration"

    async def clarify(self, snapshot: str, player_input: str) -> str:
        self.calls += 1
        return "clarify"

    async def generate_vst(self, scene_description, world_state):
        self.calls += 1
        return {"scene_id": "s1"}


@pytest.mark.asyncio
async def test_cached_llm_avoids_duplicate_calls(tmp_path: Path) -> None:
    inner = FakeLLM()
    cached = CachedLLM(inner, tmp_path / "cache.db")
    first = await cached.propose_check("snapshot", "attack")
    second = await cached.propose_check("snapshot", "attack")
    assert first == second
    assert inner.calls == 1


@pytest.mark.asyncio
async def test_json_store_round_trip(tmp_path: Path, sample_world) -> None:
    store = JsonStore(tmp_path / "sessions")
    await store.save(sample_world.session_id, sample_world)
    loaded = await store.load(sample_world.session_id)
    assert loaded == sample_world
    assert await store.list_sessions() == [sample_world.session_id]
    await store.delete(sample_world.session_id)
    assert await store.load(sample_world.session_id) is None


def test_image_cache_is_deterministic(tmp_path: Path) -> None:
    cache = ImageCache(tmp_path)
    contract = {"scene": "beach", "subjects": ["luna"]}
    image = tmp_path / "image.png"
    image.write_bytes(b"x")
    cache.put(contract, image)
    assert cache.get(contract) == image
    assert cache.get({"subjects": ["luna"], "scene": "beach"}) == image


def test_atomic_json_store_does_not_leave_tmp(tmp_path: Path, sample_world) -> None:
    store = JsonStore(tmp_path / "sessions")
    import asyncio
    asyncio.run(store.save(sample_world.session_id, sample_world))
    assert not list((tmp_path / "sessions").glob("*.tmp"))

@pytest.mark.asyncio
async def test_sqlite_store_round_trip(tmp_path, sample_world):
    from epos_v3.infrastructure.persistence.sqlite_store import SQLiteStore
    store = SQLiteStore(tmp_path / "epos.db")
    await store.save(sample_world.session_id, sample_world)
    assert await store.load(sample_world.session_id) == sample_world
    assert await store.list_sessions() == [sample_world.session_id]


@pytest.mark.asyncio
async def test_fallback_uses_secondary():
    from epos_v3.infrastructure.llm.fallback import FallbackLLM

    class Failing(FakeLLM):
        async def propose_check(self, snapshot, player_input):
            raise RuntimeError("boom")

    primary, secondary = Failing(), FakeLLM()
    result = await FallbackLLM(primary, secondary).propose_check("s", "p")
    assert result.description == "test"
    assert secondary.calls == 1


def test_json_store_recovers_last_good_backup_if_primary_is_corrupted(tmp_path, sample_world):
    import asyncio
    from epos_v3.infrastructure.persistence.json_store import JsonStore

    state = sample_world.model_copy(deep=True)
    state.session_id = "recover-json"
    store = JsonStore(tmp_path / "sessions")
    asyncio.run(store.save(state.session_id, state))
    state.turn_number = 3
    asyncio.run(store.save(state.session_id, state))

    primary = tmp_path / "sessions" / "recover-json.json"
    backup = tmp_path / "sessions" / "recover-json.json.bak"
    assert backup.exists()
    primary.write_text("{broken", encoding="utf-8")

    recovered = asyncio.run(store.load("recover-json"))

    assert recovered is not None
    assert recovered.turn_number == 0


def test_json_store_does_not_hide_corruption_without_backup(tmp_path):
    import asyncio
    import pytest
    from pydantic import ValidationError
    from epos_v3.infrastructure.persistence.json_store import JsonStore

    store = JsonStore(tmp_path / "sessions")
    path = tmp_path / "sessions" / "broken.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises((ValueError, ValidationError)):
        asyncio.run(store.load("broken"))
