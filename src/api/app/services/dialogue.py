"""A quest's conversation: stored messages, read back only by the player who wrote them.

There is no separate session table: a player's quest_progress row for a quest is that quest's
dialogue session, so every message belongs to exactly one player through it. The NPC's opening
line is stored as the first message when the quest is started (services/quests.start_quest).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dialogue import DialogueMessage
from app.models.quest_progress import QuestProgress


class DialogueNotFoundError(Exception):
    """The quest does not exist or this player has never started it."""


def get_history(db: Session, user_id: int, quest_id: int) -> list[DialogueMessage]:
    """The player's messages for one quest, oldest first."""
    progress_id = db.scalar(
        select(QuestProgress.id).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest_id)
    )
    if progress_id is None:
        raise DialogueNotFoundError
    # Ordered by id, not created_at: two messages saved in the same request share a timestamp
    return list(
        db.scalars(
            select(DialogueMessage)
            .where(DialogueMessage.quest_progress_id == progress_id)
            .order_by(DialogueMessage.id)
        )
    )
