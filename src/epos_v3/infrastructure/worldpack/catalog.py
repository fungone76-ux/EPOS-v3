"""Discovery of installable Worldpacks from a filesystem root."""

from __future__ import annotations

from pathlib import Path

import yaml


class WorldpackCatalog:
    """Map canonical Worldpack IDs to source directories."""

    def __init__(self, root: str | Path) -> None:
        """Create a catalog rooted at a directory containing Worldpack folders."""
        self.root = Path(root)

    def list_ids(self) -> list[str]:
        """Return sorted canonical IDs for folders with readable manifests."""
        return sorted(self._discover())

    def path_for(self, worldpack_id: str) -> Path | None:
        """Return the source directory for a canonical ID, if installed."""
        return self._discover().get(worldpack_id)

    def _discover(self) -> dict[str, Path]:
        """Execute the discover operation."""
        if not self.root.is_dir():
            return {}
        found: dict[str, Path] = {}
        for directory in sorted(path for path in self.root.iterdir() if path.is_dir()):
            manifest = directory / "world.yaml"
            if not manifest.is_file():
                continue
            try:
                raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(raw, dict):
                continue
            value = raw.get("world_id")
            if isinstance(value, str) and value:
                found[value] = directory
        return found
