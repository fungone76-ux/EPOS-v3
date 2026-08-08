"""Session-aware providers for NPC long-term memory stores."""

from __future__ import annotations

from epos_v3.application.npc_policy import LongTermMemoryPort

from .simple_vector import SimpleVectorMemory


class InMemoryLongTermMemoryProvider:
    """Keep one dependency-free long-term memory index per session and NPC."""

    def __init__(self) -> None:
        """Create an empty provider."""
        self._stores: dict[tuple[str, str], SimpleVectorMemory] = {}

    def for_npc(self, session_id: str, npc_id: str) -> LongTermMemoryPort:
        """Return a stable memory store for one session/NPC pair.

        Args:
            session_id: Current game session identifier.
            npc_id: Canonical NPC identifier.

        Returns:
            The existing store or a newly created dependency-free store.
        """
        key = (session_id, npc_id)
        if key not in self._stores:
            self._stores[key] = SimpleVectorMemory()
        return self._stores[key]


class ChromaLongTermMemoryProvider:
    """Create one persistent Chroma collection per session and NPC."""

    def __init__(self, persist_path: str = "./data/chroma") -> None:
        """Configure the base Chroma persistence directory.

        Args:
            persist_path: Directory used for all NPC memory collections.
        """
        self.persist_path = persist_path
        self._stores: dict[tuple[str, str], LongTermMemoryPort] = {}

    def for_npc(self, session_id: str, npc_id: str) -> LongTermMemoryPort:
        """Return a persistent Chroma memory store for one NPC.

        Args:
            session_id: Current game session identifier.
            npc_id: Canonical NPC identifier.

        Returns:
            Stable Chroma-backed memory for the pair.
        """
        from .chroma import ChromaVectorMemory

        key = (session_id, npc_id)
        if key not in self._stores:
            safe_session = session_id.replace("-", "_")
            safe_npc = npc_id.replace("-", "_")
            self._stores[key] = ChromaVectorMemory(
                collection_name=f"epos_{safe_session}_{safe_npc}",
                persist_path=self.persist_path,
            )
        return self._stores[key]
