"""Test doubles for the AI layer. They live in tests only: the running app never fakes an AI reply."""

import json

from app.content.schema import load_content
from app.models.player import EnglishLevel
from app.services.ai.prompts import DialogueContext, HistoryLine, NpcProfile, QuestBrief

VALID_REPLY = {
    "npc_reply": "That sounds great! What did you do there?",
    "communication_success": True,
    "detected_errors": [
        {
            "category": "past_simple",
            "original": "Last year I work in a restaurant.",
            "corrected": "Last year I worked in a restaurant.",
            "explanation": "Geçmişte tamamlanmış olaylarda fiilin geçmiş zaman biçimi kullanılır.",
        }
    ],
    "correctly_used": [],
    "feedback": "Good answer! Remember the past form of the verb.",
    "suggested_story_action": "interview_positive",
}


def reply_json(**changes) -> str:
    return json.dumps({**VALID_REPLY, **changes})


class FakeAiClient:
    """Returns the given replies in order; an Exception in the list is raised instead."""

    def __init__(self, *replies: str | Exception) -> None:
        self._replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        assert self._replies, "FakeAiClient was called more often than the test expected"
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def job_interview_context(
    level: EnglishLevel = EnglishLevel.B1,
    history: tuple[HistoryLine, ...] = (),
    story_summary: str = "",
) -> DialogueContext:
    """A context built from the real content files, so tests break if the content format drifts."""
    content = load_content()
    quest = next(q for q in content.quests if q.slug == "the_job_interview")
    npc = next(n for n in content.npcs if n.slug == quest.npc)
    return DialogueContext(
        npc=NpcProfile.from_content(npc, quest),
        quest=QuestBrief.from_template(quest),
        level=level,
        story_summary=story_summary,
        history=history,
    )


class FakeTransport:
    """Stands in for the HTTP layer of GeminiClient. Responses are (status, bytes) or an Exception."""

    def __init__(self, *responses: tuple[int, bytes] | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, str], bytes, float]] = []

    def __call__(self, url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
        self.calls.append((url, headers, body, timeout))
        assert self._responses, "FakeTransport was called more often than the test expected"
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def gemini_ok(text: str) -> tuple[int, bytes]:
    body = {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}
    return 200, json.dumps(body).encode()


def gemini_error(status: int, error_status: str = "", reason: str = "") -> tuple[int, bytes]:
    error: dict = {"code": status, "message": "provider text that must never be copied", "status": error_status}
    if reason:
        error["details"] = [{"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason}]
    return status, json.dumps({"error": error}).encode()
