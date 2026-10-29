"""What a quest means for one player: locked, available, active or completed.

Only the part that can be decided from the quest content exists so far: a quest without
prerequisites is available, every other quest is locked, because no player can have started or
finished anything yet. Player progress (active and completed quests, prerequisite checks against
completed quests, flags and trust) arrives with #7 and the Story Engine (#13); both extend
quest_statuses(), and callers such as the locations endpoint do not change.
"""

from collections.abc import Iterable
from enum import StrEnum

from sqlalchemy.orm import Session

from app.content.schema import Conditions
from app.models.content import QuestTemplate


class QuestStatus(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    ACTIVE = "active"
    COMPLETED = "completed"


def quest_statuses(db: Session, user_id: int, quests: Iterable[QuestTemplate]) -> dict[str, QuestStatus]:
    """The status of each quest for this player, keyed by quest slug."""
    return {
        quest.slug: QuestStatus.AVAILABLE
        if Conditions.model_validate(quest.prerequisites).is_empty()
        else QuestStatus.LOCKED
        for quest in quests
    }
