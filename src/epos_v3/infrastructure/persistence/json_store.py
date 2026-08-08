"""Atomic JSON persistence adapter."""
from __future__ import annotations
import asyncio, os, shutil
from pathlib import Path
from epos_v3.application.ports import StorePort
from epos_v3.domain.world import WorldState


class JsonStore(StorePort):
    """Persist sessions as JSON files with atomic replacement."""
    def __init__(self, base_path: str | Path = "./data/sessions") -> None:
        """Execute the init operation."""
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        """Execute the path operation."""
        if not session_id or Path(session_id).name != session_id:
            raise ValueError("Invalid session id")
        return self.base_path / f"{session_id}.json"

    async def load(self, session_id: str) -> WorldState | None:
        """Load a session, recovering the last good backup if needed."""
        path = self._path(session_id)
        if not path.exists():
            return None
        text = await asyncio.to_thread(path.read_text, encoding="utf-8")
        try:
            return WorldState.model_validate_json(text)
        except ValueError:
            backup = path.with_suffix(".json.bak")
            if not backup.exists():
                raise
            backup_text = await asyncio.to_thread(backup.read_text, encoding="utf-8")
            return WorldState.model_validate_json(backup_text)

    async def save(self, session_id: str, state: WorldState) -> None:
        """Atomically save a session while preserving the previous good snapshot."""
        path = self._path(session_id)
        payload = state.model_dump_json(indent=2)
        tmp = path.with_suffix(".tmp")
        await asyncio.to_thread(tmp.write_text, payload, encoding="utf-8")
        if path.exists():
            backup = path.with_suffix(".json.bak")
            backup_tmp = path.with_suffix(".bak.tmp")
            await asyncio.to_thread(shutil.copyfile, path, backup_tmp)
            await asyncio.to_thread(os.replace, backup_tmp, backup)
        await asyncio.to_thread(os.replace, tmp, path)

    async def list_sessions(self) -> list[str]:
        """Execute the list sessions operation."""
        paths = await asyncio.to_thread(lambda: sorted(self.base_path.glob("*.json")))
        return [p.stem for p in paths]

    async def delete(self, session_id: str) -> None:
        """Delete the primary session and its recovery backup."""
        path = self._path(session_id)
        backup = path.with_suffix(".json.bak")
        await asyncio.to_thread(path.unlink, missing_ok=True)
        await asyncio.to_thread(backup.unlink, missing_ok=True)
