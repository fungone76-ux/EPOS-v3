"""Outfit domain value objects."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutfitItem(BaseModel):
    """A single wearable item and its visual body coverage."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    slot: str
    item_id: str
    name: str
    coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    layer: int = Field(default=0, ge=0, le=5)
    material: str | None = None
    color: str | None = None
    description: str | None = None

    @field_validator("slot", "item_id", "name")
    @classmethod
    def non_empty(cls, value: str) -> str:
        """Reject empty textual fields."""
        if not value.strip():
            raise ValueError("field must not be empty")
        return value.strip()
