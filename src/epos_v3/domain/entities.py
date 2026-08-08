"""Core mutable domain entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field

from .events import TurnEvent
from .identifiers import EntityID
from .outfit import OutfitItem


class VectorStore(Protocol):
    """Port for long-term vector memory; implemented outside the domain."""

    async def search(self, query: str, limit: int = 5) -> list[str]:
        """Search stored vector memories."""
        ...

    async def add(self, text: str, metadata: dict[str, str]) -> None:
        """Add one vector memory."""
        ...


class Secret(BaseModel):
    """NPC secret and disclosure rule."""

    model_config = ConfigDict(extra="forbid")
    secret_id: str
    text: str
    disclosure_condition: str
    truthful: bool


class MemoryEntry(BaseModel):
    """A remembered event or fact."""

    model_config = ConfigDict(extra="forbid")
    turn: int
    text: str
    importance: int = Field(default=1, ge=1, le=10)


class EmotionalAssociation(BaseModel):
    """Emotion attached to a memory trigger."""

    model_config = ConfigDict(extra="forbid")
    turn: int
    emotion: str
    intensity: int = Field(ge=1, le=10)
    trigger: str


class Relationship(BaseModel):
    """Multi-dimensional relationship state."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    trust: int = Field(default=0, ge=-10, le=10)
    fear: int = Field(default=0, ge=-10, le=10)
    attraction: int = Field(default=0, ge=-10, le=10)
    resentment: int = Field(default=0, ge=-10, le=10)
    dependency: int = Field(default=0, ge=-10, le=10)
    respect: int = Field(default=0, ge=-10, le=10)
    suspicion: int = Field(default=0, ge=-10, le=10)
    history: list[tuple[int, dict[str, int]]] = Field(default_factory=list)


class Intention(BaseModel):
    """An NPC's current intended action."""

    model_config = ConfigDict(extra="forbid")
    action: str
    reason: str = ""
    priority: int = Field(default=1, ge=1, le=10)


class AgentMessage(BaseModel):
    """Message exchanged between autonomous agents."""

    model_config = ConfigDict(extra="forbid")
    sender_id: str
    recipient_id: str
    content: str
    turn: int


class RhythmConfig(BaseModel):
    """Configuration controlling autonomous NPC initiative frequency."""

    model_config = ConfigDict(extra="forbid")
    minimum_turn_gap: int = Field(default=1, ge=0)
    initiative_threshold: int = Field(default=5, ge=0, le=10)


class NPCEntity(BaseModel):
    """Self-contained NPC state and cognition container."""

    model_config = ConfigDict(validate_assignment=True, arbitrary_types_allowed=True, extra="forbid")

    entity_id: str
    name: str
    visual_gender: str = "ambiguous"
    archetype: str
    base_prompt: str
    negative_prompt: str
    character_lora: list[dict[str, object]] = Field(default_factory=list)
    role_prompt: str
    personality: str
    speech_style: str
    desires: list[str]
    fears: list[str]
    goals: list[str]
    secrets: list[Secret]
    disclosure_policy: str = ""
    red_lines: list[str]
    intimate_profile: str
    stats: dict[str, int]
    location_id: str
    is_present: bool
    is_alive: bool
    outfit: list[OutfitItem]
    conditions: list[str]
    knowledge: list[str]
    known_secrets: list[str]
    false_beliefs: list[str]
    discoveries: list[str]
    short_term_memory: list[MemoryEntry] = Field(default_factory=list)
    long_term_memory: object | None = None
    core_memories: list[MemoryEntry] = Field(default_factory=list)
    emotional_memory: dict[str, list[EmotionalAssociation]] = Field(default_factory=dict)
    relationships: dict[str, Relationship] = Field(default_factory=dict)
    intentions: list[Intention] = Field(default_factory=list)
    emotional_state: dict[str, int] = Field(default_factory=lambda: {
        "joy": 0, "anger": 0, "fear": 0, "trust": 0,
        "attraction": 0, "sadness": 0, "melancholy": 0,
    })
    perceived_events: list[TurnEvent] = Field(default_factory=list)
    last_player_action: str | None = None
    inbox: list[AgentMessage] = Field(default_factory=list)
    outbox: list[AgentMessage] = Field(default_factory=list)
    last_action_turn: int | None = None

    def perceive(self, event: TurnEvent) -> None:
        """Record an event and update immediate emotional state."""
        self.perceived_events.append(event)
        self.short_term_memory.append(MemoryEntry(turn=event.turn, text=event.description, importance=5))
        if len(self.short_term_memory) > 10:
            self.short_term_memory = self.short_term_memory[-10:]
        event_type = event.type.lower()
        if "threat" in event_type:
            self._change_emotion("fear", 3)
            self._remember_emotion(event.turn, "fear", 3, event.description)
        elif "help" in event_type:
            self._change_emotion("trust", 2)
            self._remember_emotion(event.turn, "trust", 2, event.description)
        elif "insult" in event_type:
            self._change_emotion("anger", 2)
            self._remember_emotion(event.turn, "anger", 2, event.description)

    def reason(self, context: str, n_memories: int = 5) -> list[Intention]:
        """Derive intentions from current internal values without external side effects."""
        del context
        del n_memories
        intentions: list[Intention] = []
        if self.emotional_state.get("attraction", 0) >= 8:
            intentions.append(Intention(action="sedurre", reason="high attraction", priority=8))
        if self.emotional_state.get("fear", 0) >= 7:
            intentions.append(Intention(action="fuggire", reason="high fear", priority=9))
        if self.emotional_state.get("anger", 0) >= 7:
            intentions.append(Intention(action="confrontare", reason="high anger", priority=7))
        self.intentions = sorted(intentions, key=lambda item: item.priority, reverse=True)
        return list(self.intentions)

    def should_act(self, rhythm_config: RhythmConfig, current_turn: int | None = None) -> bool:
        """Determine whether the NPC may take initiative this turn."""
        if not self.is_alive or not self.is_present:
            return False
        if current_turn is not None and self.last_action_turn is not None:
            if current_turn - self.last_action_turn < rhythm_config.minimum_turn_gap:
                return False
        return bool(self.intentions and self.intentions[0].priority >= rhythm_config.initiative_threshold)

    def generate_response(self, player_input: str, world_state: object) -> str:
        """Produce a domain-safe response placeholder for an outer narrative adapter."""
        del world_state
        return f"{self.name} reagisce a: {player_input}"

    def update_relationship(self, other_id: str, delta: dict[str, int], reason: str) -> None:
        """Apply bounded relationship changes and antagonistic trust/suspicion coupling."""
        relationship = self.relationships.setdefault(other_id, Relationship())
        normalized = dict(delta)
        if "trust" in normalized:
            normalized["suspicion"] = normalized.get("suspicion", 0) - normalized["trust"]
        if "suspicion" in delta:
            normalized["trust"] = normalized.get("trust", 0) - delta["suspicion"]
        for field_name, change in normalized.items():
            if field_name not in Relationship.model_fields or field_name == "history":
                raise ValueError(f"unknown relationship dimension: {field_name}")
            current = getattr(relationship, field_name)
            setattr(relationship, field_name, max(-10, min(10, current + change)))
        relationship.history.append((len(self.perceived_events), dict(delta)))
        if reason:
            self.short_term_memory.append(MemoryEntry(turn=len(self.perceived_events), text=reason, importance=5))
            self.short_term_memory = self.short_term_memory[-10:]

    def _change_emotion(self, emotion: str, delta: int) -> None:
        """Execute the change emotion operation."""
        current = self.emotional_state.get(emotion, 0)
        self.emotional_state[emotion] = max(0, min(10, current + delta))

    def _remember_emotion(self, turn: int, emotion: str, intensity: int, trigger: str) -> None:
        """Execute the remember emotion operation."""
        self.emotional_memory.setdefault(emotion, []).append(
            EmotionalAssociation(turn=turn, emotion=emotion, intensity=intensity, trigger=trigger)
        )


class Player(BaseModel):
    """Player-controlled entity."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    entity_id: str | EntityID
    name: str
    visual_gender: str = "ambiguous"
    outfit: list[OutfitItem]
    stats: dict[str, int]
    inventory: list[str]
    location_id: str
    conditions: list[str]
    knowledge: list[str]
    relationships: dict[str, Relationship] = Field(default_factory=dict)
    notes: str | None = None

    def get_coverage_by_slot(self, slot: str) -> float:
        """Calculate layered coverage for one outfit slot."""
        coverage = 0.0
        for item in sorted((i for i in self.outfit if i.slot == slot), key=lambda i: i.layer):
            coverage += item.coverage * (1.0 - coverage)
        return coverage

    def is_naked(self) -> bool:
        """Return whether both primary body regions have zero coverage."""
        return self.get_coverage_by_slot("torso") == 0.0 and self.get_coverage_by_slot("legs") == 0.0
