from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

PLAYER_MESSAGE_MAX_LENGTH = 500


class MessageRole(StrEnum):
    PLAYER = "player"
    NPC = "npc"


class DialogueMessage(Base):
    """One line of a quest's conversation. The quest_progress row is the dialogue session."""

    __tablename__ = "dialogue_messages"
    __table_args__ = (
        CheckConstraint(
            f"role IN ({', '.join(repr(r.value) for r in MessageRole)})",
            name="ck_dialogue_messages_role",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quest_progress_id: Mapped[int] = mapped_column(
        ForeignKey("quest_progress.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(6))
    text: Mapped[str] = mapped_column(Text)
    # Set only on player messages: did the NPC understand what the player meant (grammar aside)
    communication_success: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
