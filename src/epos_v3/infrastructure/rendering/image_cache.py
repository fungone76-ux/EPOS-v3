"""Deterministic image cache."""
from __future__ import annotations
import hashlib, json, os
from pathlib import Path
from epos_v3.domain.types import JSONObject


class ImageCache:
    """Map a visual contract hash to an existing image path."""
    def __init__(self, cache_dir: str | Path = "./data/render_cache") -> None:
        """Execute the init operation."""
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.cache_dir / "index.json"
        self.index = self._load_index()

    @staticmethod
    def _hash(visual_contract: JSONObject) -> str:
        """Execute the hash operation."""
        return hashlib.sha256(json.dumps(visual_contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _load_index(self) -> dict[str, str]:
        """Execute the load index operation."""
        if not self.index_path.exists():
            return {}
        try:
            value = json.loads(self.index_path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}

    def get(self, visual_contract: JSONObject) -> Path | None:
        """Execute the get operation."""
        path = self.index.get(self._hash(visual_contract))
        if path and Path(path).exists():
            return Path(path)
        return None

    def put(self, visual_contract: JSONObject, image_path: str | Path) -> None:
        """Execute the put operation."""
        self.index[self._hash(visual_contract)] = str(image_path)
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.index, sort_keys=True, indent=2), encoding="utf-8")
        os.replace(tmp, self.index_path)
