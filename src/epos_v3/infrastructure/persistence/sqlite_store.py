"""SQLite persistence using the Python standard library."""
from __future__ import annotations
import asyncio, sqlite3
from pathlib import Path
from epos_v3.application.ports import StorePort
from epos_v3.domain.world import WorldState


class SQLiteStore(StorePort):
    """Persist world states in SQLite without blocking the event loop."""
    def __init__(self, db_path: str | Path = "./data/epos_v3.db") -> None:
        """Execute the init operation."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Execute the init db operation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, worldpack_id TEXT NOT NULL, state_json TEXT NOT NULL)")

    async def load(self, session_id: str) -> WorldState | None:
        """Execute the load operation."""
        def read() -> str | None:
            """Execute the read operation."""
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT state_json FROM sessions WHERE id = ?", (session_id,)).fetchone()
                return str(row[0]) if row else None
        value = await asyncio.to_thread(read)
        return WorldState.model_validate_json(value) if value else None

    async def save(self, session_id: str, state: WorldState) -> None:
        """Execute the save operation."""
        payload = state.model_dump_json()
        def write() -> None:
            """Execute the write operation."""
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT INTO sessions(id, worldpack_id, state_json) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET worldpack_id=excluded.worldpack_id, state_json=excluded.state_json", (session_id, state.worldpack_id, payload))
        await asyncio.to_thread(write)

    async def list_sessions(self) -> list[str]:
        """Execute the list sessions operation."""
        def read() -> list[str]:
            """Execute the read operation."""
            with sqlite3.connect(self.db_path) as conn:
                return [str(row[0]) for row in conn.execute("SELECT id FROM sessions ORDER BY id")]
        return await asyncio.to_thread(read)

    async def delete(self, session_id: str) -> None:
        """Execute the delete operation."""
        def remove() -> None:
            """Execute the remove operation."""
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        await asyncio.to_thread(remove)
