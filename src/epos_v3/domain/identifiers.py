"""Domain identifiers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class EntityID:
    """Canonical identifier for a world entity."""

    value: str
    _pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9_]*$")

    def __post_init__(self) -> None:
        """Normalize and validate the identifier."""
        normalized = self.value.strip().lower().replace(" ", "_").replace("-", "_")
        if not self._pattern.fullmatch(normalized):
            raise ValueError(f"Invalid entity_id: {normalized!r}")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        """Return the canonical string value."""
        return self.value
