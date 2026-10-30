from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
