from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.placeholders import not_implemented
from app.models.user import User
from app.schemas.player import ProfileResponse, ProfileUpdateRequest
from app.services.players import get_profile as find_profile
from app.services.players import save_profile

router = APIRouter(prefix="/player", tags=["player"])


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Return the logged-in player's character."""
    profile = find_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Create your character first.",
        )
    return ProfileResponse.model_validate(profile)


@router.put(
    "/profile",
    response_model=ProfileResponse,
    responses={status.HTTP_201_CREATED: {"description": "Character created"}},
)
def update_profile(
    payload: ProfileUpdateRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileResponse:
    """Create the character on the first call (201) and update it afterwards (200)."""
    profile, created = save_profile(db, current_user.id, payload)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return ProfileResponse.model_validate(profile)


@router.get("/progress")
def get_progress():
    raise not_implemented("Player progress")
