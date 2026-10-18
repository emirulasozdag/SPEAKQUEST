from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.placeholders import not_implemented
from app.schemas.auth import RegisterRequest, UserResponse
from app.services.users import EmailAlreadyRegisteredError, create_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserResponse:
    """Create an account. The password is stored only as a bcrypt hash."""
    try:
        user = create_user(db, email=payload.email, password=payload.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None
    return UserResponse.model_validate(user)


@router.post("/login")
def login():
    raise not_implemented("Login")


@router.get("/me")
def me():
    raise not_implemented("Current user")
