"""Password hashing and access tokens. Plain-text passwords are never stored or logged."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

TOKEN_ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=TOKEN_ALGORITHM)


def read_access_token(token: str) -> int:
    """Return the user id inside a valid token; raise InvalidTokenError otherwise."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=[TOKEN_ALGORITHM])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as error:
        raise InvalidTokenError from error
