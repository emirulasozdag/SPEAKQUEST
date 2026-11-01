"""User account operations, kept out of the routers so they can be reused and tested."""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.dialogue import DialogueMessage
from app.models.learning import LanguageError, SkillObservation
from app.models.player import PlayerProfile
from app.models.quest_progress import QuestProgress
from app.models.story import NpcRelationship, StoryDecision, StoryState
from app.models.user import User

# Every model that stores data of one player, keyed by user_id. A PR that adds such a table
# adds it here too; tests/test_account_deletion.py fails when one is missing.
# The rows are deleted explicitly as well as through ON DELETE CASCADE, so deletion does not
# depend on the database enforcing foreign keys (SQLite does not by default).
# Learning rows point at dialogue messages, so they come before them
PLAYER_DATA_MODELS = (
    LanguageError,
    SkillObservation,
    PlayerProfile,
    QuestProgress,
    StoryState,
    NpcRelationship,
    StoryDecision,
)


class EmailAlreadyRegisteredError(Exception):
    pass


# Checked when the email is unknown, so a failed login takes the same time either way
# and response times do not reveal which emails have accounts.
_DUMMY_PASSWORD_HASH = hash_password("speakquest-timing-guard")


def create_user(db: Session, email: str, password: str) -> User:
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise EmailAlreadyRegisteredError(email)

    user = User(email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        # Two requests with the same email can pass the check above at the same time
        db.rollback()
        raise EmailAlreadyRegisteredError(email) from error
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Return the user when the email and password match, otherwise None."""
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def delete_account(db: Session, user: User, password: str) -> bool:
    """Delete the account and all of its player data in one transaction.

    Returns False and deletes nothing when the password is wrong.
    """
    if not verify_password(password, user.password_hash):
        return False
    for model in PLAYER_DATA_MODELS:
        if model is QuestProgress:
            # Messages hang off quest_progress, not users: they go after the learning rows that
            # point at them and before their own parent rows
            db.execute(
                delete(DialogueMessage).where(
                    DialogueMessage.quest_progress_id.in_(
                        select(QuestProgress.id).where(QuestProgress.user_id == user.id)
                    )
                )
            )
        db.execute(delete(model).where(model.user_id == user.id))
    db.delete(user)
    db.commit()
    return True
