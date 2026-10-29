"""What a quest means for one player: locked, available, active or completed, and starting one.

Two things are stored per player, nothing else: a quest_progress row exists once a quest was
started (status active or completed). Whether an untouched quest is locked or available is
computed on every request by the Story Engine's is_unlocked(), so it can never go stale.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.content.schema import Conditions
from app.engines.story import StoryProgress, is_unlocked
from app.models.content import QuestTemplate
from app.models.quest_progress import QuestProgress, QuestProgressStatus


class QuestStatus(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"


class QuestNotFoundError(Exception):
    pass


class QuestStartRefusedError(Exception):
    """The quest exists but cannot be started now. `reason` is stable, `message` is for the player."""

    def __init__(
        self,
        reason: Literal["locked", "already_active", "already_completed", "another_active"],
        message: str,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class PlayerQuest:
    quest: QuestTemplate
    status: QuestStatus
    progress: QuestProgress | None


def load_story_progress(db: Session, user_id: int) -> StoryProgress:
    """The player's story state as the Story Engine's unlock rule needs it.

    Completed quests come from quest_progress. Flags and NPC trust stay empty until the Story
    Engine stores them (#13, #17); a quest that needs one is simply locked until then.
    """
    completed = db.scalars(
        select(QuestTemplate.slug)
        .join(QuestProgress, QuestProgress.quest_template_id == QuestTemplate.id)
        .where(QuestProgress.user_id == user_id, QuestProgress.status == QuestProgressStatus.COMPLETED)
    )
    return StoryProgress(completed_quests=frozenset(completed))


def quest_statuses(db: Session, user_id: int, quests: Iterable[QuestTemplate]) -> dict[str, QuestStatus]:
    """The status of each quest for this player, keyed by quest slug."""
    quests = list(quests)
    progress_by_quest = _progress_by_quest(db, user_id)
    story = load_story_progress(db, user_id)
    return {quest.slug: _status_of(quest, progress_by_quest.get(quest.id), story) for quest in quests}


def list_player_quests(db: Session, user_id: int) -> list[PlayerQuest]:
    quests = db.scalars(
        select(QuestTemplate)
        .options(selectinload(QuestTemplate.location), selectinload(QuestTemplate.npc))
        .order_by(QuestTemplate.chapter, QuestTemplate.id)
    ).all()
    progress_by_quest = _progress_by_quest(db, user_id)
    story = load_story_progress(db, user_id)
    return [
        PlayerQuest(quest, _status_of(quest, progress_by_quest.get(quest.id), story), progress_by_quest.get(quest.id))
        for quest in quests
    ]


def get_active_quest(db: Session, user_id: int) -> PlayerQuest | None:
    progress = db.scalar(
        select(QuestProgress)
        .where(QuestProgress.user_id == user_id, QuestProgress.status == QuestProgressStatus.ACTIVE)
        .options(
            selectinload(QuestProgress.quest).selectinload(QuestTemplate.location),
            selectinload(QuestProgress.quest).selectinload(QuestTemplate.npc),
        )
    )
    return None if progress is None else PlayerQuest(progress.quest, QuestStatus.ACTIVE, progress)


def start_quest(db: Session, user_id: int, quest_id: int) -> PlayerQuest:
    """Start a quest for this player or raise why it cannot be started."""
    quest = db.scalar(
        select(QuestTemplate)
        .where(QuestTemplate.id == quest_id)
        .options(selectinload(QuestTemplate.location), selectinload(QuestTemplate.npc))
    )
    if quest is None:
        raise QuestNotFoundError

    existing = db.scalar(
        select(QuestProgress).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest.id)
    )
    if existing is not None:
        raise _already_started(existing)
    if not is_unlocked(Conditions.model_validate(quest.prerequisites), load_story_progress(db, user_id)):
        raise QuestStartRefusedError("locked", "This quest is still locked. Finish the earlier quests first.")
    if get_active_quest(db, user_id) is not None:
        raise QuestStartRefusedError("another_active", "Finish your active quest before starting another one.")

    progress = QuestProgress(user_id=user_id, quest_template_id=quest.id, status=QuestProgressStatus.ACTIVE)
    db.add(progress)
    try:
        db.commit()
    except IntegrityError:
        # Two requests raced past the checks above; the database constraints decide who won
        db.rollback()
        existing = db.scalar(
            select(QuestProgress).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest.id)
        )
        if existing is not None:
            raise _already_started(existing) from None
        raise QuestStartRefusedError(
            "another_active", "Finish your active quest before starting another one."
        ) from None
    db.refresh(progress)
    return PlayerQuest(quest, QuestStatus.ACTIVE, progress)


def _already_started(progress: QuestProgress) -> QuestStartRefusedError:
    if progress.status == QuestProgressStatus.COMPLETED:
        return QuestStartRefusedError("already_completed", "You have already completed this quest.")
    return QuestStartRefusedError("already_active", "This quest is already active.")


def _progress_by_quest(db: Session, user_id: int) -> dict[int, QuestProgress]:
    rows = db.scalars(select(QuestProgress).where(QuestProgress.user_id == user_id))
    return {row.quest_template_id: row for row in rows}


def _status_of(quest: QuestTemplate, progress: QuestProgress | None, story: StoryProgress) -> QuestStatus:
    if progress is not None:
        return QuestStatus.COMPLETED if progress.status == QuestProgressStatus.COMPLETED else QuestStatus.ACTIVE
    unlocked = is_unlocked(Conditions.model_validate(quest.prerequisites), story)
    return QuestStatus.AVAILABLE if unlocked else QuestStatus.LOCKED
