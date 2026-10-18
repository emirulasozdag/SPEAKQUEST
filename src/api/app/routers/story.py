from fastapi import APIRouter

from app.core.placeholders import not_implemented

router = APIRouter(prefix="/story", tags=["story"])


@router.get("/state")
def story_state():
    raise not_implemented("Story state")


@router.post("/decision")
def story_decision():
    raise not_implemented("Story decisions")
