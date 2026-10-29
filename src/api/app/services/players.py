"""Player profile operations, kept out of the routers so they can be reused and tested."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.player import PlayerProfile
from app.schemas.player import ProfileUpdateRequest


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
