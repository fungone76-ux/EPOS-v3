"""Check proposal and resolution value objects."""

from __future__ import annotations

from enum import StrEnum
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .dice import DiceResult, OutcomeLevel


class CheckType(StrEnum):
    """Supported phase-one proposal types."""

    NO_CHECK = "no_check"
    CHECK_PROPOSAL = "check_proposal"
    CONFRONT_PROPOSAL = "confront_proposal"
    CLARIFICATION = "clarification"


class OutfitRequest(BaseModel):
    """Player request for an NPC outfit change, interpreted but not committed by the LLM."""

    model_config = ConfigDict(extra="forbid")
    target_id: str
    wear_terms: list[str] = Field(default_factory=list)
    remove_terms: list[str] = Field(default_factory=list)

    @field_validator("wear_terms", "remove_terms", mode="before")
    @classmethod
    def _normalize_terms(cls, value: object) -> object:
        """Accept a single LLM string while keeping the runtime contract list-based."""
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        return value


class CheckProposal(BaseModel):
    """LLM-produced proposal that Python validates and resolves."""

    model_config = ConfigDict(extra="forbid")
    check_type: CheckType = CheckType.CHECK_PROPOSAL
    description: str = ""
    skill: str | None = None
    difficulty: int = Field(default=1, ge=1, le=6)
    target_ids: list[str] = Field(default_factory=list)
    destination_location_id: str | None = None
    opposition: str = "none"
    stakes: dict[str, str] = Field(default_factory=dict)
    triggers: list[str] = Field(default_factory=list)
    outfit_requests: list[OutfitRequest] = Field(default_factory=list)


class ResolvedCheck(BaseModel):
    """Authoritative result of a validated check."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
    proposal: CheckProposal
    pool_size: int = Field(ge=0)
    dice: DiceResult
    choice: str
    mutations: list[dict[str, object]] = Field(default_factory=list)

    @property
    def outcome(self) -> OutcomeLevel:
        """Return the authoritative dice outcome."""
        return self.dice.outcome
