"""User account operations, kept out of the routers so they can be reused and tested."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


class EmailAlreadyRegisteredError(Exception):
    pass


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
