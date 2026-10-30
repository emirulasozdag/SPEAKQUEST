from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import RateLimiter, client_ip, raise_if_limited
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.users import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    create_user,
    delete_account,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed logins are counted per email + IP, so one attacker cannot lock other people out
login_limiter = RateLimiter()
register_limiter = RateLimiter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest, request: Request, db: Session = Depends(get_db)
) -> UserResponse:
    """Create an account. The password is stored only as a bcrypt hash."""
    settings = get_settings()
    ip_key = client_ip(request)
    raise_if_limited(
        register_limiter, ip_key, settings.register_rate_limit, settings.register_rate_window_seconds
    )
    register_limiter.hit(ip_key, settings.register_rate_window_seconds)
    try:
        user = create_user(db, email=payload.email, password=payload.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    """Exchange email and password for an access token."""
    settings = get_settings()
    attempt_key = f"{payload.email}|{client_ip(request)}"
    # Checked before the password, so a blocked caller learns nothing about the account
    raise_if_limited(
        login_limiter, attempt_key, settings.login_rate_limit, settings.login_rate_window_seconds
    )

    user = authenticate_user(db, email=payload.email, password=payload.password)
    if user is None:
        login_limiter.hit(attempt_key, settings.login_rate_window_seconds)
        # Same answer for an unknown email and a wrong password, so accounts cannot be probed
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    login_limiter.reset(attempt_key)
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the account that the access token belongs to."""
    return UserResponse.model_validate(current_user)


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(
    payload: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Permanently delete the account and all of the player's data. Needs the current password."""
    if not delete_account(db, current_user, payload.password):
        # 403, not 401: the session is still valid, only the confirmation failed
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
