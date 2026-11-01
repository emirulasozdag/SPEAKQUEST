"""Loading one player's learning records for the Learning Engine (engines/learning.py).

The engine works on Observation values; this module reads skill_observations, the player's own
messages and language_errors, always filtered by the logged-in player's user_id. Nothing here
writes: the dialogue flow records mistakes through engines.learning.record_message_analysis().
"""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.engines.categories import SkillCategory
from app.engines.learning import (
    RECENT_PRACTICE_MESSAGES,
    REPEAT_WINDOW_MESSAGES,
    LearningTarget,
    Observation,
    SkillScore,
    TimelinePoint,
    rank_learning_targets,
    score_timeline,
    skill_scores,
)
from app.models.content import QuestTemplate
from app.models.dialogue import DialogueMessage, MessageRole
from app.models.learning import LanguageError, ObservationResult, SkillObservation
from app.models.player import EnglishLevel
from app.models.quest_progress import QuestProgress

# Enough of the player's latest messages for both windows of the engine
RECENT_WINDOW = max(REPEAT_WINDOW_MESSAGES, RECENT_PRACTICE_MESSAGES)


def load_observations(db: Session, user_id: int) -> list[Observation]:
    """Every skill opportunity of the player, oldest first."""
    rows = db.execute(
        select(
            SkillObservation.category,
            SkillObservation.result,
            SkillObservation.message_id,
            SkillObservation.created_at,
        )
        .where(SkillObservation.user_id == user_id)
        .order_by(SkillObservation.id)
    )
    return [
        Observation(SkillCategory(category), result == ObservationResult.CORRECT, message_id, created_at)
        for category, result, message_id, created_at in rows
    ]


def recent_message_ids(db: Session, user_id: int, limit: int = RECENT_WINDOW) -> list[int]:
    """The ids of the player's own latest messages, newest first, across all quests."""
    return list(
        db.scalars(
            select(DialogueMessage.id)
            .join(QuestProgress, QuestProgress.id == DialogueMessage.quest_progress_id)
            .where(QuestProgress.user_id == user_id, DialogueMessage.role == MessageRole.PLAYER)
            .order_by(DialogueMessage.id.desc())
            .limit(limit)
        )
    )


def get_skill_scores(db: Session, user_id: int) -> dict[SkillCategory, SkillScore]:
    return skill_scores(load_observations(db, user_id), recent_message_ids(db, user_id))


def get_timeline(db: Session, user_id: int) -> list[TimelinePoint]:
    """Each skill's score at the end of every day the player practised (score_timeline)."""
    return score_timeline(load_observations(db, user_id))


def get_learning_targets(db: Session, user_id: int, level: EnglishLevel) -> list[LearningTarget]:
    """Every skill, best next learning target first."""
    return rank_learning_targets(get_skill_scores(db, user_id), level)


@dataclass(frozen=True)
class ErrorEntry:
    error: LanguageError
    quest_id: int
    quest_title: str


def get_errors(
    db: Session, user_id: int, category: SkillCategory | None, limit: int, offset: int
) -> tuple[list[ErrorEntry], int]:
    """The player's mistakes, newest first, with the quest they were made in, and the total."""
    conditions = [LanguageError.user_id == user_id]
    if category is not None:
        conditions.append(LanguageError.category == category)
    total = db.scalar(select(func.count()).select_from(LanguageError).where(*conditions))
    rows = db.execute(
        select(LanguageError, QuestTemplate.id, QuestTemplate.title)
        .join(DialogueMessage, DialogueMessage.id == LanguageError.message_id)
        .join(QuestProgress, QuestProgress.id == DialogueMessage.quest_progress_id)
        .join(QuestTemplate, QuestTemplate.id == QuestProgress.quest_template_id)
        .where(*conditions)
        .order_by(LanguageError.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [ErrorEntry(error, quest_id, title) for error, quest_id, title in rows], total
