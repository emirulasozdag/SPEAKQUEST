"""Shared FastAPI dependencies for protected endpoints."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import InvalidTokenError, read_access_token
from app.models.user import User

# auto_error=False so a missing token gets the same 401 as an invalid one (not FastAPI's 403)
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the logged-in user from the `Authorization: Bearer <token>` header."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="You need to log in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = read_access_token(credentials.credentials)
    except InvalidTokenError:
        raise unauthorized from None

    user = db.get(User, claims.user_id)
    # A token from before the last password change no longer opens the account
    if user is None or claims.version != user.token_version:
        raise unauthorized
    return user
