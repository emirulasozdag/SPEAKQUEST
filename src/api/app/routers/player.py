from fastapi import APIRouter

from app.core.placeholders import not_implemented

router = APIRouter(prefix="/player", tags=["player"])


@router.get("/profile")
def get_profile():
    raise not_implemented("Player profile")


@router.put("/profile")
def update_profile():
    raise not_implemented("Player profile update")


@router.get("/progress")
def get_progress():
    raise not_implemented("Player progress")
