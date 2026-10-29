from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EnglishLevel(StrEnum):
    A2 = "A2"
    B1 = "B1"


class LearningGoal(StrEnum):
    EVERYDAY = "everyday"
    WORK = "work"
    GRAMMAR = "grammar"


AVATAR_COUNT = 3
CHARACTER_NAME_MAX_LENGTH = 30


def _one_of(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(value.value) for value in values)})"


class PlayerProfile(Base):
    """The player's character. XP and level are changed only by backend game rules."""

    __tablename__ = "player_profiles"
    __table_args__ = (
        CheckConstraint(f"avatar BETWEEN 1 AND {AVATAR_COUNT}", name="ck_player_profiles_avatar"),
        CheckConstraint(_one_of("english_level", EnglishLevel), name="ck_player_profiles_english_level"),
        CheckConstraint(_one_of("learning_goal", LearningGoal), name="ck_player_profiles_learning_goal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    character_name: Mapped[str] = mapped_column(String(CHARACTER_NAME_MAX_LENGTH))
    avatar: Mapped[int] = mapped_column(SmallInteger)
    english_level: Mapped[str] = mapped_column(String(2))
    learning_goal: Mapped[str] = mapped_column(String(20))
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    level: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
