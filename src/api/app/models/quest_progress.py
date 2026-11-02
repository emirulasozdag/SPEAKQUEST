from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.content import QuestTemplate


class QuestProgressStatus(StrEnum):
    """Only what is stored. 'locked' and 'available' are computed by the Story Engine."""

    ACTIVE = "active"
    COMPLETED = "completed"


class QuestProgress(Base):
    """One player's attempt at one quest. It is also that quest's dialogue session (#11)."""

    __tablename__ = "quest_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "quest_template_id", name="uq_quest_progress_user_quest"),
        CheckConstraint(
            f"status IN ({', '.join(repr(s.value) for s in QuestProgressStatus)})",
            name="ck_quest_progress_status",
        ),
        # The database itself refuses a second active quest for the same player, even when two
        # requests arrive at the same moment
        Index(
            "uq_quest_progress_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    quest_template_id: Mapped[int] = mapped_column(ForeignKey("quest_templates.id"))
    status: Mapped[str] = mapped_column(String(12))
    # Objective ids the backend has verified; never written from what the client or the AI claims
    objectives_met: Mapped[list] = mapped_column(JSON, default=list)
    # Trust that story actions in this quest's conversation added; capped by the Story Engine
    story_trust_gained: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # XP given on completion; a non-zero value stops the same quest paying twice
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    quest: Mapped[QuestTemplate] = relationship()
