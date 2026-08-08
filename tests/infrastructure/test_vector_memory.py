from __future__ import annotations

import pytest

from epos_v3.infrastructure.memory.simple_vector import SimpleVectorMemory
from epos_v3.infrastructure.memory.chroma import ChromaVectorMemory


def test_simple_vector_memory_recalls_relevant_text() -> None:
    memory = SimpleVectorMemory()
    memory.add("Victoria ha parlato del debito bancario", turn=3, tags=["victoria", "debito"], importance=8)
    memory.add("Luna ha passeggiato sulla spiaggia", turn=4, tags=["luna", "spiaggia"], importance=4)

    recalled = memory.recall("problema del debito di Victoria", n=1)

    assert recalled == ["Victoria ha parlato del debito bancario"]


def test_simple_vector_memory_prefers_importance_on_equal_relevance() -> None:
    memory = SimpleVectorMemory()
    memory.add("evento alpha", turn=1, tags=["alpha"], importance=2)
    memory.add("evento alpha importante", turn=2, tags=["alpha"], importance=9)

    recalled = memory.recall("alpha", n=1)

    assert recalled == ["evento alpha importante"]


def test_chroma_adapter_fails_clearly_when_optional_dependency_is_missing() -> None:
    try:
        import chromadb  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError, match="chromadb"):
            ChromaVectorMemory(collection_name="test")
