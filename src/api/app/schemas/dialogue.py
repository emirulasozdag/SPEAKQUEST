from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.engines.categories import SkillCategory
from app.models.dialogue import MessageRole


class CorrectionOut(BaseModel):
    category: SkillCategory
    original: str
    corrected: str
    # One short sentence in Turkish
    explanation: str


class DialogueMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: MessageRole
    text: str
    # Only on player messages; null for the NPC
    communication_success: bool | None
    created_at: datetime
    # Only filled when the history is read: the mistakes found in this player message. A turn
    # answer carries its corrections at the top level instead.
    corrections: list["CorrectionOut"] = []


class DialogueSummaryOut(BaseModel):
    """What a quest's conversation showed. Built only from stored messages and mistakes."""

    quest_id: int
    messages_sent: int
    understood: int
    mistakes: int
    # Most frequent mistake category, null when the player made none
    top_category: SkillCategory | None
    # One to three corrections (empty when there were no mistakes)
    examples: list["CorrectionOut"]


class DialogueHistoryOut(BaseModel):
    quest_id: int
    messages: list[DialogueMessageOut]


class SendMessageRequest(BaseModel):
    # Length and emptiness are checked by the service after trimming, so the player gets one
    # clear sentence instead of a validation list
    message: str


class StoryActionOut(BaseModel):
    """What the AI suggested for the story and whether the Story Engine allowed it."""

    suggested: str
    accepted: bool


class ObjectiveStateOut(BaseModel):
    id: str
    description: str
    # Set only by the backend; the AI's claim is checked first (engines/objectives.py)
    met: bool


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
    # Every objective of the quest with its state after this message (met and still open), and the
    # ids this message fulfilled for the first time. Empty when the AI was unavailable.
    objectives: list[ObjectiveStateOut] = []
    newly_met: list[str] = []
    player_message: DialogueMessageOut | None = None
    npc_message: DialogueMessageOut | None = None
