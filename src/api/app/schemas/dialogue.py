from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.engines.categories import SkillCategory
from app.models.dialogue import MessageRole


class DialogueMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    text: str
    # Only on player messages; null for the NPC
    communication_success: bool | None
    created_at: datetime


class DialogueHistoryOut(BaseModel):
    quest_id: int
    messages: list[DialogueMessageOut]


class SendMessageRequest(BaseModel):
    # Length and emptiness are checked by the service after trimming, so the player gets one
    # clear sentence instead of a validation list
    message: str


class CorrectionOut(BaseModel):
    category: SkillCategory
    original: str
    corrected: str
    # One short sentence in Turkish
    explanation: str


class StoryActionOut(BaseModel):
    """What the AI suggested for the story and whether the Story Engine allowed it."""

    suggested: str
    accepted: bool


class DialogueTurnOut(BaseModel):
    # "ai_unavailable": the NPC answered with a fallback line, nothing was saved, try again
    status: Literal["ok", "ai_unavailable"]
    quest_id: int
    npc_reply: str
    # Whether the NPC understood the player; judged apart from grammar. Null when AI was unavailable.
    communication_success: bool | None = None
    corrections: list[CorrectionOut] = []
    feedback: str = ""
    story_action: StoryActionOut | None = None
    player_message: DialogueMessageOut | None = None
    npc_message: DialogueMessageOut | None = None
