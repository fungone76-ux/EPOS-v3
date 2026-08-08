import pytest

from epos_v3.infrastructure.context.compression import SnapshotCompressor
from epos_v3.infrastructure.context.project_memory import ProjectMemory


def test_compressor_reduces_large_snapshot(sample_world):
    sample_world.history_digest = "important" * 5000
    compressed = SnapshotCompressor().compress(sample_world, max_tokens=200)
    assert len(compressed) <= 800


@pytest.mark.asyncio
async def test_project_memory_round_trip(tmp_path):
    path = tmp_path / "memory.json"
    memory = ProjectMemory(completed_modules=["domain"], in_progress="infra")
    await memory.save(path)
    loaded = await ProjectMemory.load(path)
    assert loaded.completed_modules == ["domain"]
    assert loaded.in_progress == "infra"


def test_compressed_snapshot_keeps_world_skill_catalog(sample_world):
    sample_world.skill_definitions = {"hacking": "Accesso ai sistemi", "pilotaggio": "Controllo veicoli"}
    sample_world.history_digest = "x" * 5000

    compressed = SnapshotCompressor().compress(sample_world, max_tokens=200)

    assert '"skill_definitions"' in compressed
    assert '"hacking"' in compressed
