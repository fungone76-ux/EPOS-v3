"""Deterministic cleanup helpers for Stable Diffusion prompt assembly."""

from __future__ import annotations

import re


_BOORU_REMOVE = {
    "1girl",
    "2girls",
    "3girls",
    "1boy",
    "2boys",
    "3boys",
}

_ACTION_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(greet|greets|greeting|salut|saluta|saluto)\b", re.IGNORECASE), "greeting"),
    (re.compile(r"\b(speak|speaks|talk|talks|conversation|dialogue|parla|conversa)\b", re.IGNORECASE), "conversation"),
    (re.compile(r"\b(sit|sits|seated|sedut[oa]|siede)\b", re.IGNORECASE), "seated"),
    (re.compile(r"\b(cross(?:es|ed)?\s+(?:her\s+|his\s+)?legs|accavalla)\b", re.IGNORECASE), "crossed legs"),
    (re.compile(r"\b(remov(?:e|es|ing)|takes? off|toglie|sfila).{0,16}(shoe|shoes|scarpa|scarpe|heel|heels)\b", re.IGNORECASE), "removing high heel"),
)


def sanitize_character_tags(text: str) -> str:
    """Remove only unwanted Booru counting tags while preserving authored traits."""
    tags = _split_tags(text)
    kept = [tag for tag in tags if tag.lower() not in _BOORU_REMOVE]
    return ", ".join(_dedupe(kept))


def compact_action_tags(description: str, interaction: str) -> list[str]:
    """Reduce narrative action prose to short deterministic visual tags."""
    combined = f"{description} {interaction}".strip()
    tags: list[str] = []
    for pattern, replacement in _ACTION_RULES:
        if pattern.search(combined):
            tags.append(replacement)
    return _dedupe(tags)


def dedupe_prompt_tags(text: str) -> str:
    """Deduplicate comma-separated prompt tags case-insensitively."""
    return ", ".join(_dedupe(_split_tags(text)))


def _split_tags(text: str) -> list[str]:
    ignored = {"none", "null", "n/a"}
    return [
        part.strip()
        for part in text.split(",")
        if part.strip() and part.strip().casefold() not in ignored
    ]


def _dedupe(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        key = tag.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
    return result
