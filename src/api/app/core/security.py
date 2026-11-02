"""Password hashing and access tokens. Plain-text passwords are never stored or logged."""

from dataclasses import dataclass
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


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    # The account's token_version when the token was issued; a password change raises it, so
    # every older token stops working
    version: int


def create_access_token(user_id: int, version: int = 0) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "ver": version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=TOKEN_ALGORITHM)


def read_access_token(token: str) -> TokenClaims:
    """Return the claims of a valid token; raise InvalidTokenError otherwise.

    A token without an expiry, subject or issue time is invalid, never "valid forever".
    """
    try:
        payload = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[TOKEN_ALGORITHM],
            options={"require": ["exp", "sub", "iat"]},
        )
        return TokenClaims(user_id=int(payload["sub"]), version=int(payload.get("ver", 0)))
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as error:
        raise InvalidTokenError from error
