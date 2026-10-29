from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.player import EnglishLevel


def _level_in(column: str) -> str:
    return f"{column} IN ({', '.join(repr(level.value) for level in EnglishLevel)})"


class Location(Base):
    """A place on the map. Content, not player data: loaded from content files by the seed command.

    Whether a place is locked for a player is never stored; it is computed from the player's state.
    """

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    sort_order: Mapped[int]

    npcs: Mapped[list["Npc"]] = relationship(back_populates="location", order_by="Npc.id")
    quests: Mapped[list["QuestTemplate"]] = relationship(
        back_populates="location", order_by=lambda: (QuestTemplate.chapter, QuestTemplate.id)
    )


class Npc(Base):
    """A character the player talks to. personality, speaking_style and knows go into the AI prompt
    only; they are never returned by the API (knows can contain story spoilers)."""

    __tablename__ = "npcs"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    name: Mapped[str] = mapped_column(String(60))
    role: Mapped[str] = mapped_column(String(80))
    personality: Mapped[str] = mapped_column(Text)
    speaking_style: Mapped[str] = mapped_column(Text)
    knows: Mapped[list] = mapped_column(JSON)

    location: Mapped[Location] = relationship(back_populates="npcs")


class QuestTemplate(Base):
    """A quest as written in app/content/quests/<slug>.json. A queryable copy of that file."""

    __tablename__ = "quest_templates"
    __table_args__ = (
        CheckConstraint(_level_in("min_level"), name="ck_quest_templates_min_level"),
        CheckConstraint(_level_in("max_level"), name="ck_quest_templates_max_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    chapter: Mapped[int]
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    npc_id: Mapped[int] = mapped_column(ForeignKey("npcs.id"))
    target_skills: Mapped[list] = mapped_column(JSON)
    min_level: Mapped[str] = mapped_column(String(2))
    max_level: Mapped[str] = mapped_column(String(2))
    summary: Mapped[str] = mapped_column(Text)
    npc_opening: Mapped[str] = mapped_column(Text)
    objectives: Mapped[list] = mapped_column(JSON)
    prerequisites: Mapped[dict] = mapped_column(JSON)
    rewards: Mapped[dict] = mapped_column(JSON)
    allowed_story_actions: Mapped[list] = mapped_column(JSON)
    decision_points: Mapped[list] = mapped_column(JSON)

    location: Mapped[Location] = relationship(back_populates="quests")
    npc: Mapped[Npc] = relationship()
