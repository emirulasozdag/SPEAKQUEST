"""What a quest means for one player: locked, available, active or completed; starting and
completing one.

Two things are stored per player, nothing else: a quest_progress row exists once a quest was
started (status active or completed). Whether an untouched quest is locked or available is
computed on every request by the Story Engine's is_unlocked(), so it can never go stale.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.content.schema import Conditions
from app.engines.progression import XpGain, add_xp
from app.engines.story import StoryProgress, is_unlocked
from app.models.content import QuestTemplate
from app.models.dialogue import DialogueMessage, MessageRole
from app.models.quest_progress import QuestProgress, QuestProgressStatus
from app.services.players import get_profile


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


class QuestCompleteRefusedError(Exception):
    """The quest exists but cannot be completed now. `reason` is stable, `message` is for the player."""

    def __init__(
        self,
        reason: Literal["not_started", "already_completed", "objectives_not_met", "no_character"],
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
    quest = _load_quest(db, quest_id)

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
        db.flush()
        # Every conversation opens with the NPC's line from the template, saved with the quest
        db.add(DialogueMessage(quest_progress_id=progress.id, role=MessageRole.NPC, text=quest.npc_opening))
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


@dataclass(frozen=True)
class CompletedQuest:
    item: PlayerQuest
    gain: XpGain


def complete_quest(db: Session, user_id: int, quest_id: int) -> CompletedQuest:
    """Complete the player's active quest and pay its XP once, or raise why it cannot be completed.

    Only the quest's objectives decide: every objective id must be in objectives_met, which the
    backend fills while checking the conversation. Grammar mistakes never block completion, and
    nothing the client sends is trusted.
    """
    quest = _load_quest(db, quest_id)
    progress = db.scalar(
        select(QuestProgress).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest.id)
    )
    if progress is None:
        raise QuestCompleteRefusedError("not_started", "Start this quest before completing it.")
    if progress.status == QuestProgressStatus.COMPLETED:
        raise _already_completed()
    met = set(progress.objectives_met)
    if any(objective["id"] not in met for objective in quest.objectives):
        raise QuestCompleteRefusedError(
            "objectives_not_met", "You have not reached every objective of this quest yet."
        )
    profile = get_profile(db, user_id)
    if profile is None:
        raise QuestCompleteRefusedError("no_character", "Create your character before completing a quest.")

    reward = quest.rewards["xp"]
    # Only the request that flips the row from active to completed pays; a second request for the
    # same quest waits on this row lock and then finds nothing left to update
    flipped = db.execute(
        update(QuestProgress)
        .where(QuestProgress.id == progress.id, QuestProgress.status == QuestProgressStatus.ACTIVE)
        .values(status=QuestProgressStatus.COMPLETED, completed_at=datetime.now(timezone.utc), xp_awarded=reward)
    ).rowcount
    if flipped != 1:
        db.rollback()
        raise _already_completed()

    # One active quest per player, so no other completion can change this profile meanwhile
    gain = add_xp(profile.xp, reward)
    profile.xp = gain.xp
    profile.level = gain.level
    db.commit()
    db.refresh(progress)
    return CompletedQuest(PlayerQuest(quest, QuestStatus.COMPLETED, progress), gain)


def _load_quest(db: Session, quest_id: int) -> QuestTemplate:
    quest = db.scalar(
        select(QuestTemplate)
        .where(QuestTemplate.id == quest_id)
        .options(selectinload(QuestTemplate.location), selectinload(QuestTemplate.npc))
    )
    if quest is None:
        raise QuestNotFoundError
    return quest


def _already_completed() -> QuestCompleteRefusedError:
    return QuestCompleteRefusedError("already_completed", "You have already completed this quest.")


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
