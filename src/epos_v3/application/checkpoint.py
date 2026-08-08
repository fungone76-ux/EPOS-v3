"""Atomic checkpoint persistence for post-roll resume."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import cast
import aiofiles
from epos_v3.domain.checks import CheckProposal, ResolvedCheck
from epos_v3.domain.dice import DiceResult
from epos_v3.domain.types import JSONObject
from epos_v3.domain.world import WorldState
from .ports import StorePort

class CheckpointService:
    """Persist proposal and resolved roll before narration/commit."""
    def __init__(self, store: StorePort, root: Path | str = "saves") -> None:
        """Execute the init operation."""
        self._store = store
        self._root = Path(root)

    async def save(self, session_id: str, state: WorldState, proposal: CheckProposal, resolved: ResolvedCheck) -> None:
        """Write a checkpoint atomically."""
        directory = self._root / session_id
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "checkpoint.json"
        tmp = directory / "checkpoint.json.tmp"
        checkpoint: JSONObject = {
            "session_id": session_id,
            "turn_number": state.turn_number,
            "state": state.model_dump(mode="json"),
            "proposal": proposal.model_dump(mode="json"),
            "resolved": {
                "pool_size": resolved.pool_size,
                "pool": list(resolved.dice.pool),
                "threshold": resolved.dice.threshold,
                "outcome": resolved.outcome.value,
                "player_choice": resolved.choice,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        async with aiofiles.open(tmp, "w", encoding="utf-8") as handle:
            await handle.write(json.dumps(checkpoint, indent=2, ensure_ascii=False))
        tmp.replace(path)

    async def resume(self, session_id: str) -> JSONObject | None:
        """Load the latest checkpoint, if present."""
        path = self._root / session_id / "checkpoint.json"
        if not path.exists():
            return None
        async with aiofiles.open(path, "r", encoding="utf-8") as handle:
            return cast(JSONObject, json.loads(await handle.read()))
    async def restore(self, session_id: str) -> tuple[WorldState, CheckProposal, ResolvedCheck] | None:
        """Rebuild authoritative turn objects from a saved checkpoint.

        The stored dice pool is reused exactly; this method never rolls dice.
        """
        checkpoint = await self.resume(session_id)
        if checkpoint is None:
            return None
        state = WorldState.model_validate(checkpoint["state"])
        proposal = CheckProposal.model_validate(checkpoint["proposal"])
        saved = checkpoint["resolved"]
        dice = DiceResult(
            saved.get("pool", []),
            threshold=int(saved.get("threshold", proposal.difficulty)),
        )
        resolved = ResolvedCheck(
            proposal=proposal,
            pool_size=int(saved.get("pool_size", len(dice.pool))),
            dice=dice,
            choice=str(saved.get("player_choice", "safe")),
        )
        return state, proposal, resolved

    async def clear(self, session_id: str) -> None:
        """Remove a completed turn checkpoint and any temporary file."""
        directory = self._root / session_id
        for name in ("checkpoint.json", "checkpoint.json.tmp"):
            path = directory / name
            if path.exists():
                path.unlink()
        if directory.exists() and not any(directory.iterdir()):
            directory.rmdir()

