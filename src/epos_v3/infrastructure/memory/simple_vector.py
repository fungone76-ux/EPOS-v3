"""Dependency-free deterministic vector-like memory fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9_]+")


@dataclass(frozen=True)
class _Entry:
    """One local long-term memory entry."""

    text: str
    turn: int
    tags: tuple[str, ...]
    importance: int
    tokens: frozenset[str]


class SimpleVectorMemory:
    """Recall memories by deterministic token similarity and importance.

    This adapter is intentionally dependency-free. It gives EPOS a graceful
    long-term-memory fallback when ChromaDB is not installed.
    """

    def __init__(self) -> None:
        """Create an empty in-memory store."""
        self._entries: list[_Entry] = []

    def add(self, text: str, turn: int, tags: list[str], importance: int) -> None:
        """Add one memory to the local index.

        Args:
            text: Human-readable remembered event.
            turn: Turn in which the event happened.
            tags: Semantic tags associated with the event.
            importance: Importance score from 1 to 10.
        """
        if not text.strip():
            return
        normalized_importance = max(1, min(10, importance))
        tokens = _tokens(" ".join([text, *tags]))
        self._entries.append(
            _Entry(
                text=text,
                turn=turn,
                tags=tuple(tags),
                importance=normalized_importance,
                tokens=tokens,
            )
        )

    def recall(self, context: str, n: int = 5) -> list[str]:
        """Return the most relevant memories for a context.

        Args:
            context: Current reasoning context.
            n: Maximum number of memories to return.

        Returns:
            Memory texts ordered by relevance, importance, then recency.
        """
        if n <= 0:
            return []
        query = _tokens(context)
        ranked = sorted(
            self._entries,
            key=lambda entry: (
                len(query & entry.tokens),
                entry.importance,
                _similarity(query, entry.tokens),
                entry.turn,
            ),
            reverse=True,
        )
        relevant = [entry.text for entry in ranked if _similarity(query, entry.tokens) > 0]
        return relevant[:n]


def _tokens(text: str) -> frozenset[str]:
    """Normalize text into a deterministic token set."""
    return frozenset(match.group(0).casefold() for match in _TOKEN_RE.finditer(text))


def _similarity(left: frozenset[str], right: frozenset[str]) -> float:
    """Compute Jaccard similarity between two token sets."""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)
