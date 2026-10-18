"""User account operations, kept out of the routers so they can be reused and tested."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User


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
