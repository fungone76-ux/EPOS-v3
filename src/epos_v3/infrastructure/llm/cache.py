"""SQLite exact-response cache for LLM calls."""
from __future__ import annotations
import asyncio, hashlib, json, sqlite3
from pathlib import Path
from epos_v3.application.ports import LLMPort
from epos_v3.domain.checks import CheckProposal
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState


class CachedLLM(LLMPort):
    """Cache deterministic requests before calling the wrapped LLM."""
    def __init__(self, inner: LLMPort, db_path: str | Path = "./data/llm_cache.db") -> None:
        """Execute the init operation."""
        self.inner, self.db_path = inner, Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Execute the init db operation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS llm_cache (hash TEXT PRIMARY KEY, response TEXT NOT NULL)")

    @staticmethod
    def _hash(*parts: str) -> str:
        """Execute the hash operation."""
        return hashlib.sha256("::".join(parts).encode()).hexdigest()

    async def _get(self, key: str) -> str | None:
        """Execute the get operation."""
        def read() -> str | None:
            """Execute the read operation."""
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT response FROM llm_cache WHERE hash = ?", (key,)).fetchone()
                return str(row[0]) if row else None
        return await asyncio.to_thread(read)

    async def _set(self, key: str, response: str) -> None:
        """Execute the set operation."""
        def write() -> None:
            """Execute the write operation."""
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR REPLACE INTO llm_cache(hash, response) VALUES (?, ?)", (key, response))
        await asyncio.to_thread(write)

    async def propose_check(self, snapshot: str, player_input: str) -> CheckProposal:
        """Execute the propose check operation."""
        key = self._hash("propose", snapshot, player_input)
        cached = await self._get(key)
        if cached is not None:
            return CheckProposal.model_validate_json(cached)
        result = await self.inner.propose_check(snapshot, player_input)
        await self._set(key, result.model_dump_json())
        return result

    async def narrate_scene(self, snapshot: str, resolved_outcome: str) -> str:
        """Execute the narrate scene operation."""
        key = self._hash("narrate", snapshot, resolved_outcome)
        cached = await self._get(key)
        if cached is not None:
            return json.loads(cached)
        result = await self.inner.narrate_scene(snapshot, resolved_outcome)
        await self._set(key, json.dumps(result))
        return result

    async def clarify(self, snapshot: str, player_input: str) -> str:
        """Execute the clarify operation."""
        key = self._hash("clarify", snapshot, player_input)
        cached = await self._get(key)
        if cached is not None:
            return json.loads(cached)
        result = await self.inner.clarify(snapshot, player_input)
        await self._set(key, json.dumps(result))
        return result

    async def generate_vst(self, scene_description: str, world_state: WorldState) -> JSONObject:
        """Execute the generate vst operation."""
        key = self._hash("vst", scene_description, world_state.model_dump_json())
        cached = await self._get(key)
        if cached is not None:
            return json.loads(cached)
        result = await self.inner.generate_vst(scene_description, world_state)
        await self._set(key, json.dumps(result, sort_keys=True))
        return result
