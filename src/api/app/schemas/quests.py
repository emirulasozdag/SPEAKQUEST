from datetime import datetime

from pydantic import BaseModel

from app.engines.categories import SkillCategory
from app.services.quests import PlayerQuest, QuestStatus


class QuestSummaryOut(BaseModel):
    """A quest as the player sees it in lists. Story data (NPC opening line, prerequisites,
    decisions) stays on the server."""

    id: int
    slug: str
    title: str
    chapter: int
    summary: str
    location_slug: str
    npc_slug: str
    status: QuestStatus
    target_skills: list[SkillCategory]
    reward_xp: int
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_player_quest(cls, item: PlayerQuest) -> "QuestSummaryOut":
        quest, progress = item.quest, item.progress
        return cls(
            id=quest.id,
            slug=quest.slug,
            title=quest.title,
            chapter=quest.chapter,
            summary=quest.summary,
            location_slug=quest.location.slug,
            npc_slug=quest.npc.slug,
            status=item.status,
            target_skills=quest.target_skills,
            reward_xp=quest.rewards["xp"],
            started_at=progress.started_at if progress else None,
            completed_at=progress.completed_at if progress else None,
        )


class ObjectiveOut(BaseModel):
    id: str
    description: str
    # Set only by the backend when it has verified the objective
    met: bool


class ActiveQuestOut(QuestSummaryOut):
    objectives: list[ObjectiveOut]

    @classmethod
    def from_player_quest(cls, item: PlayerQuest) -> "ActiveQuestOut":
        base = QuestSummaryOut.from_player_quest(item)
        met = set(item.progress.objectives_met) if item.progress else set()
        return cls(
            **base.model_dump(),
            objectives=[
                ObjectiveOut(id=o["id"], description=o["description"], met=o["id"] in met)
                for o in item.quest.objectives
            ],
        )
