"""Optional ChromaDB adapter for persistent NPC long-term memory."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4


class _Collection(Protocol):
    """Small subset of the Chroma collection API used by EPOS."""

    def add(
        self,
        *,
        documents: list[str],
        metadatas: list[dict[str, str | int]],
        ids: list[str],
    ) -> None:
        """Add documents to the Chroma collection."""
        ...

    def query(self, *, query_texts: list[str], n_results: int) -> dict[str, object]:
        """Query documents by semantic similarity."""
        ...


class ChromaVectorMemory:
    """Persist and retrieve long-term memories through ChromaDB."""

    def __init__(
        self,
        collection_name: str,
        persist_path: str | Path = "./data/chroma",
    ) -> None:
        """Create a Chroma-backed memory store.

        Args:
            collection_name: Stable collection identifier, normally session + NPC.
            persist_path: Directory used by ChromaDB for persistence.

        Raises:
            RuntimeError: If the optional ``chromadb`` dependency is unavailable.
        """
        try:
            import chromadb
        except ImportError as exc:
            raise RuntimeError(
                "chromadb is required for ChromaVectorMemory; install EPOS with [ai-memory]"
            ) from exc
        client = chromadb.PersistentClient(path=str(persist_path))
        self._collection = cast(_Collection, client.get_or_create_collection(name=collection_name))

    def add(self, text: str, turn: int, tags: list[str], importance: int) -> None:
        """Persist one long-term memory.

        Args:
            text: Remembered event.
            turn: Source turn number.
            tags: Semantic tags serialized into metadata.
            importance: Importance score used for diagnostics/re-ranking.
        """
        self._collection.add(
            documents=[text],
            metadatas=[
                {
                    "turn": turn,
                    "importance": max(1, min(10, importance)),
                    "tags": ",".join(tags),
                }
            ],
            ids=[str(uuid4())],
        )

    def recall(self, context: str, n: int = 5) -> list[str]:
        """Retrieve semantically similar memory texts.

        Args:
            context: Current NPC reasoning context.
            n: Maximum number of memories.

        Returns:
            Retrieved document texts in Chroma relevance order.
        """
        if n <= 0:
            return []
        result = self._collection.query(query_texts=[context], n_results=n)
        documents = result.get("documents")
        if not isinstance(documents, list) or not documents:
            return []
        first = documents[0]
        if not isinstance(first, list):
            return []
        return [item for item in first if isinstance(item, str)]
