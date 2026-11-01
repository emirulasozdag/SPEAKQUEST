from datetime import datetime

from pydantic import BaseModel

from app.engines.categories import SkillCategory
from app.services.quests import CompletedQuest, PlayerQuest, QuestStatus


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


class QuestListItemOut(QuestSummaryOut):
    """A quest in the list, marked when the Adaptive Quest Engine recommends it as the next one."""

    recommended: bool = False
    # Why the engine picked it, for the player; set only on the recommended quest
    recommendation_reason: str | None = None
    # What the player still needs before the quest opens; set only on locked quests
    locked_reason: str | None = None


class EndingOut(BaseModel):
    slug: str
    title: str
    summary: str


class QuestCompletedOut(BaseModel):
    """The finished quest and what it paid. XP and level are the player's new totals."""

    quest: QuestSummaryOut
    xp_gained: int
    xp: int
    level: int
    leveled_up: bool
    # Set when this was the last quest the player could play and the story has ended
    ending: EndingOut | None = None

    @classmethod
    def from_completed(cls, completed: CompletedQuest) -> "QuestCompletedOut":
        gain = completed.gain
        return cls(
            quest=QuestSummaryOut.from_player_quest(completed.item),
            xp_gained=gain.gained,
            xp=gain.xp,
            level=gain.level,
            leveled_up=gain.leveled_up,
            ending=(
                EndingOut(slug=completed.ending.slug, title=completed.ending.title, summary=completed.ending.summary)
                if completed.ending
                else None
            ),
        )
