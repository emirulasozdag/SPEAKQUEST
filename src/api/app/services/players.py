"""Player profile operations, kept out of the routers so they can be reused and tested."""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.dialogue import DialogueMessage
from app.models.learning import LanguageError, SkillObservation
from app.models.player import PlayerProfile
from app.models.quest_progress import QuestProgress
from app.models.story import NpcRelationship, StoryDecision, StoryState
from app.schemas.player import ProfileUpdateRequest
from app.services.story import get_story_state, new_story_state


# Every table that holds one player's game and learning progress, keyed by user_id. Resetting the
# game clears all of them; deleting the account clears them and then the character and account.
# A PR that adds a table with player data adds it here (tests/test_account.py checks this).
# Learning rows point at dialogue messages, so they come first. Rows are deleted explicitly as
# well as through ON DELETE CASCADE, so this does not depend on the database enforcing foreign
# keys (SQLite does not by default).
PROGRESS_MODELS = (
    LanguageError,
    SkillObservation,
    QuestProgress,
    StoryDecision,
    NpcRelationship,
    StoryState,
)


def get_profile(db: Session, user_id: int) -> PlayerProfile | None:
    return db.scalar(select(PlayerProfile).where(PlayerProfile.user_id == user_id))


def save_profile(db: Session, user_id: int, data: ProfileUpdateRequest) -> tuple[PlayerProfile, bool]:
    """Create the user's profile or update the character fields of the existing one.

    Returns the profile and whether it was newly created. XP and level are never touched here.
    """
    profile = get_profile(db, user_id)
    created = profile is None
    if created:
        profile = PlayerProfile(user_id=user_id)
        db.add(profile)
        # The story starts once, with the character; editing the character later never resets it
        if get_story_state(db, user_id) is None:
            db.add(new_story_state(user_id))

    _apply_character_fields(profile, data)
    try:
        db.commit()
    except IntegrityError:
        # Two first-time requests can both try to create the profile; the loser updates instead
        db.rollback()
        profile = get_profile(db, user_id)
        if profile is None:
            raise
        created = False
        _apply_character_fields(profile, data)
        db.commit()
    db.refresh(profile)
    return profile, created


def _apply_character_fields(profile: PlayerProfile, data: ProfileUpdateRequest) -> None:
    profile.character_name = data.character_name
    profile.avatar = data.avatar
    profile.english_level = data.english_level
    profile.learning_goal = data.learning_goal


def delete_progress(db: Session, user_id: int) -> None:
    """Delete every progress row of this player (PROGRESS_MODELS). Does not commit."""
    for model in PROGRESS_MODELS:
        if model is QuestProgress:
            # Messages belong to quest_progress, not to users, so they go just before it
            db.execute(
                delete(DialogueMessage).where(
                    DialogueMessage.quest_progress_id.in_(select(QuestProgress.id).where(QuestProgress.user_id == user_id))
                )
            )
        db.execute(delete(model).where(model.user_id == user_id))


def reset_progress(db: Session, user_id: int) -> PlayerProfile | None:
    """Start the game again: all progress is deleted in one transaction, the story starts over,
    XP and level go back to the start. The account and the character stay.

    Returns None (and changes nothing) when the player has no character yet.
    """
    profile = get_profile(db, user_id)
    if profile is None:
        return None
    delete_progress(db, user_id)
    db.add(new_story_state(user_id))
    profile.xp = 0
    profile.level = 1
    db.commit()
    db.refresh(profile)
    return profile
