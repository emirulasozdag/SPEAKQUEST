from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.engines.categories import SkillCategory


def _one_of(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(value.value) for value in values)})"


class ObservationResult(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"


class LanguageError(Base):
    """One mistake the AI found in a player message. Written only by the Learning Engine."""

    __tablename__ = "language_errors"
    __table_args__ = (
        CheckConstraint(_one_of("category", SkillCategory), name="ck_language_errors_category"),
        Index("ix_language_errors_user_category", "user_id", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message_id: Mapped[int] = mapped_column(ForeignKey("dialogue_messages.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(30))
    original: Mapped[str] = mapped_column(Text)
    corrected: Mapped[str] = mapped_column(Text)
    # One short sentence in Turkish
    explanation: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SkillObservation(Base):
    """A message gave the player a chance to use a skill, and they got it right or wrong.

    One row per category per message; a message that never touched a skill has no row for it,
    so a sentence without a past tense does not change the Past Simple score (#16).
    """

    __tablename__ = "skill_observations"
    __table_args__ = (
        CheckConstraint(_one_of("category", SkillCategory), name="ck_skill_observations_category"),
        CheckConstraint(_one_of("result", ObservationResult), name="ck_skill_observations_result"),
        Index("ix_skill_observations_user_category_created", "user_id", "category", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    message_id: Mapped[int] = mapped_column(ForeignKey("dialogue_messages.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(30))
    result: Mapped[str] = mapped_column(String(9))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
