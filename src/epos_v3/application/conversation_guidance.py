"""Deterministic conversation goals for grounded NPC dialogue."""

from __future__ import annotations

from enum import StrEnum


class ConversationGoal(StrEnum):
    """High-level purpose that one NPC reply should advance."""

    INFORM = "inform"
    RELATE = "relate"
    ESCALATE_TENSION = "escalate_tension"
    SEEK_DECISION = "seek_decision"


_FACTUAL_MARKERS = (
    "chi ",
    "che ",
    "cosa ",
    "come ",
    "dove ",
    "quando ",
    "quale ",
    "quali ",
    "perché ",
    "perche ",
    "raccontami",
    "spiegami",
    "dimmi",
    "leggenda",
    "storia",
    "sai?",
    "sai ",
)

_DECISION_MARKERS = (
    "accetti",
    "rifiuti",
    "decidi",
    "scegli",
    "sei d'accordo",
    "sei d’accordo",
    "vuoi farlo",
    "che ne dici della proposta",
)

_TENSION_MARKERS = (
    "ti sfido",
    "non ti credo",
    "stai mentendo",
    "dimostralo",
    "provamelo",
    "minaccio",
)


def conversation_goal_for(player_input: str) -> ConversationGoal:
    """Classify the next conversational purpose from player-visible text.

    This classification does not decide NPC state or outcomes. It only tells the
    narrator which dimension the reply should advance.

    Args:
        player_input: Raw player utterance/action text.

    Returns:
        The deterministic high-level goal for the next NPC reply.
    """
    normalized = " ".join(player_input.casefold().split())
    if any(marker in normalized for marker in _DECISION_MARKERS):
        return ConversationGoal.SEEK_DECISION
    if any(marker in normalized for marker in _TENSION_MARKERS):
        return ConversationGoal.ESCALATE_TENSION
    if "?" in normalized or any(marker in normalized for marker in _FACTUAL_MARKERS):
        return ConversationGoal.INFORM
    return ConversationGoal.RELATE


def conversation_directive(player_input: str) -> dict[str, str]:
    """Build narration instructions for one dynamic conversational goal.

    Args:
        player_input: Raw player utterance/action text.

    Returns:
        JSON-safe goal and requirements for the narration adapter.
    """
    goal = conversation_goal_for(player_input)
    if goal is ConversationGoal.INFORM:
        requirements = (
            "Answer the player's direct question first. Give 1-3 concrete facts from the "
            "available NPC knowledge or world reference. Respect disclosure_policy and never "
            "reveal a blocked fact. If the available context does not contain the answer, say "
            "exactly what is unknown. Do not substitute mystery, metaphor, philosophy, or an "
            "unrelated goal for an answer. The reply must advance information."
        )
    elif goal is ConversationGoal.SEEK_DECISION:
        requirements = (
            "Move the exchange toward a concrete choice or position. State the NPC's current "
            "answer when the authoritative context supports one; otherwise identify the exact "
            "condition still preventing a decision. The reply must advance a decision."
        )
    elif goal is ConversationGoal.ESCALATE_TENSION:
        requirements = (
            "Respond to the challenge concretely through an observable reaction, boundary, "
            "counter-demand, warning, or concession. The reply must advance tension rather "
            "than hiding behind generic atmosphere."
        )
    else:
        requirements = (
            "Develop the relationship through a specific reaction, personal detail, question, "
            "boundary, preference, or offer grounded in the current context. Avoid generic "
            "philosophical filler. The reply must advance the relationship."
        )
    return {"goal": goal.value, "requirements": requirements}
