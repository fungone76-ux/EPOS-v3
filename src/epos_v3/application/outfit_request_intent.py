"""Semantic filtering for LLM outfit-request proposals."""

from __future__ import annotations

import re

from epos_v3.domain.checks import CheckProposal


_EXPLICIT_CHANGE_RE = re.compile(
    r"\b(indossa|indossare|metti|mettiti|mettere|togli|togliti|togliere|sfila|"
    r"sfilati|levati|leva|cambia|cambiare|sostituisci|sostituire|wear|put on|"
    r"remove|take off)\b",
    re.IGNORECASE,
)

_WITHOUT_CLOTHING_RE = re.compile(
    r"\bsenza\s+(?:quel|quella|il|lo|la|i|gli|le|un|una|dei|delle)?\s*"
    r"(costume|vestito|abito|scarpe|scarpa|stivali|sandali|pumps|heels|"
    r"calze|collant|pantyhose|stockings|bikini|top|gonna|dress|shoes?)\b",
    re.IGNORECASE,
)


def sanitize_outfit_requests(
    proposal: CheckProposal,
    player_input: str,
) -> CheckProposal:
    """Drop outfit mutations when the player's text did not request clothing changes."""
    if not proposal.outfit_requests:
        return proposal
    normalized = player_input.strip()
    if _EXPLICIT_CHANGE_RE.search(normalized) or _WITHOUT_CLOTHING_RE.search(normalized):
        return proposal
    cleaned = proposal.model_copy(deep=True)
    cleaned.outfit_requests = []
    return cleaned
