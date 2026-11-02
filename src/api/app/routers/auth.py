from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limit import RateLimiter, client_ip, raise_if_limited
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.users import (
    EmailAlreadyRegisteredError,
    authenticate_user,
    change_password,
    create_user,
    delete_account,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Failed logins are counted per email + IP, so one attacker cannot lock other people out
login_limiter = RateLimiter()
register_limiter = RateLimiter()
# Wrong current passwords on a logged-in account, counted per user
password_check_limiter = RateLimiter()


def _check_password_attempts(user: User) -> str:
    """Answer 429 when this account has used up its password attempts; returns its limiter key."""
    settings = get_settings()
    key = f"user:{user.id}"
    raise_if_limited(
        password_check_limiter, key, settings.password_check_rate_limit, settings.password_check_rate_window_seconds
    )
    return key


def _count_wrong_password(key: str) -> None:
    password_check_limiter.hit(key, get_settings().password_check_rate_window_seconds)


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
        access_token=create_access_token(user.id, user.token_version),
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
    attempts = _check_password_attempts(current_user)
    if not delete_account(db, current_user, payload.password):
        _count_wrong_password(attempts)
        # 403, not 401: the session is still valid, only the confirmation failed
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Incorrect password.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", response_model=TokenResponse)
def change_my_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Replace the password after checking the current one. The new one follows the sign-up rules.

    Every session opened before ends; this one continues with the new token in the response.
    """
    attempts = _check_password_attempts(current_user)
    if not change_password(db, current_user, payload.current_password, payload.new_password):
        _count_wrong_password(attempts)
        # 403, not 401: the session is still valid, only the check failed
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your current password is incorrect.")
    password_check_limiter.reset(attempts)
    return TokenResponse(
        access_token=create_access_token(current_user.id, current_user.token_version),
        expires_in=get_settings().access_token_expire_minutes * 60,
    )
