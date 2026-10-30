from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.engines.trust import TRUST_MAX, TRUST_MIN
from app.models.content import Location, Npc


class StoryState(Base):
    """Where one player is in the story. Created once, together with the character."""

    __tablename__ = "story_states"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    chapter: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    # Where the player last went to play a quest; null until the first quest is started
    current_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"))
    # Flag slugs set by the player's decisions (#17), e.g. ["helped_alex"]
    flags: Mapped[list] = mapped_column(JSON, default=list)
    # Slug of the ending the player reached (#21); null while the story goes on
    ending: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    current_location: Mapped[Location | None] = relationship()


class NpcRelationship(Base):
    """How much one NPC trusts one player. A missing row means trust 0."""

    __tablename__ = "npc_relationships"
    __table_args__ = (
        UniqueConstraint("user_id", "npc_id", name="uq_npc_relationships_user_npc"),
        CheckConstraint(f"trust BETWEEN {TRUST_MIN} AND {TRUST_MAX}", name="ck_npc_relationships_trust"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    npc_id: Mapped[int] = mapped_column(ForeignKey("npcs.id"))
    trust: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    npc: Mapped[Npc] = relationship()
