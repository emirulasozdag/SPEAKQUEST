"""Turns one player message into an AnalysisResult: the NPC reply plus the language analysis.

This module never touches the database or the game state. It cannot: it takes a client, a context
and a message, and returns data. XP, level, quest completion and the story are decided elsewhere
(progression, Story Engine), and `suggested_story_action` here is only a suggestion that the Story
Engine checks against the quest's allowed actions (#13).

If the AI is missing, down or answers with something unusable, the result has status
"ai_unavailable" and a safe fallback reply; callers must then change nothing in the game (#12).
"""

import logging
from dataclasses import dataclass
from typing import Literal

from app.services.ai.client import AiClient, AiError
from app.services.ai.prompts import DialogueContext, Prompt, build_prompt, build_repair_prompt
from app.services.ai.schemas import AnalysisFailure, DialogueAnalysis, parse_analysis

logger = logging.getLogger("speakquest.ai")

# Neutral on purpose: it fits any scene and says nothing about scores or the story
FALLBACK_NPC_REPLY = "Sorry, I lost my train of thought for a moment. Could you say that again?"

UnavailableReason = Literal["not_configured", "provider_error", "invalid_reply"]


@dataclass(frozen=True)
class AnalysisResult:
    status: Literal["ok", "ai_unavailable"]
    npc_reply: str
    # Present only when status is "ok"
    analysis: DialogueAnalysis | None = None
    # Present only when status is "ai_unavailable"; a short code, never provider text
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def analyze_message(client: AiClient | None, context: DialogueContext, player_message: str) -> AnalysisResult:
    """Ask the AI once, and once more if its reply does not fit the schema. Never raises."""
    if client is None:
        return _unavailable("not_configured")

    prompt = build_prompt(context, player_message)
    try:
        outcome = _validated_reply(client, prompt)
        if isinstance(outcome, AnalysisFailure):
            # One correction attempt, repeating only our own validation message (not the bad reply)
            outcome = _validated_reply(client, build_repair_prompt(prompt, outcome))
    except AiError as exc:
        return _unavailable(exc.reason)

    if isinstance(outcome, AnalysisFailure):
        return _unavailable("invalid_reply", detail=outcome.reason)
    return AnalysisResult(status="ok", npc_reply=outcome.npc_reply, analysis=outcome)


def _validated_reply(client: AiClient, prompt: Prompt) -> DialogueAnalysis | AnalysisFailure:
    return parse_analysis(client.complete(prompt.system, prompt.user))


def _unavailable(reason: str, detail: str = "") -> AnalysisResult:
    logger.warning("ai unavailable reason=%s%s", reason, f" detail={detail}" if detail else "")
    return AnalysisResult(status="ai_unavailable", npc_reply=FALLBACK_NPC_REPLY, reason=reason)
