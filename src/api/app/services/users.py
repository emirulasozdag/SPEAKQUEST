"""User account operations, kept out of the routers so they can be reused and tested."""

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.player import PlayerProfile
from app.models.user import User
from app.services.players import PROGRESS_MODELS, delete_progress

# Every model that stores data of one player, keyed by user_id: the game and learning progress
# (services/players.py) plus the character itself. tests/test_account_deletion.py fails when a
# table that points at users is missing here.
PLAYER_DATA_MODELS = (*PROGRESS_MODELS, PlayerProfile)


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
    delete_progress(db, user.id)
    db.execute(delete(PlayerProfile).where(PlayerProfile.user_id == user.id))
    db.delete(user)
    db.commit()
    return True


def change_password(db: Session, user: User, current_password: str, new_password: str) -> bool:
    """Store a new bcrypt hash and end every existing session.

    Returns False and changes nothing when the current password is wrong.
    """
    if not verify_password(current_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    # Every session opened with the old password ends here (see core/dependencies.py)
    user.token_version += 1
    db.commit()
    return True
