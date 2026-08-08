"""Persistent project progress memory."""
from __future__ import annotations
import asyncio, json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class ProjectMemory:
    """Track completed modules, decisions, questions, and test status."""
    project: str = "EPOS v3"
    completed_modules: list[str] = field(default_factory=list)
    in_progress: str = ""
    design_decisions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    test_status: dict[str, str] = field(default_factory=dict)

    async def save(self, path: str | Path = "./project_memory.json") -> None:
        """Save project memory atomically."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self), indent=2, ensure_ascii=False)
        tmp = target.with_suffix(".tmp")
        await asyncio.to_thread(tmp.write_text, payload, encoding="utf-8")
        await asyncio.to_thread(tmp.replace, target)

    @classmethod
    async def load(cls, path: str | Path = "./project_memory.json") -> "ProjectMemory":
        """Load project memory or return an empty memory when absent."""
        target = Path(path)
        if not target.exists():
            return cls()
        text = await asyncio.to_thread(target.read_text, encoding="utf-8")
        return cls(**json.loads(text))
