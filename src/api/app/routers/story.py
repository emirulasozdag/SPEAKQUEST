from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.placeholders import not_implemented
from app.models.user import User
from app.schemas.story import NpcRelationshipOut, StoryLocationOut, StoryStateOut
from app.services import story as story_service

router = APIRouter(prefix="/story", tags=["story"])


@router.get("/state", response_model=StoryStateOut)
def story_state(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StoryStateOut:
    """The logged-in player's chapter, location, flags, ending and trust with every NPC.

    404 until the character is created, because the story starts with the character.
    """
    state = story_service.get_story_state(db, current_user.id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Create your character first.")
    location = state.current_location
    return StoryStateOut(
        chapter=state.chapter,
        current_location=StoryLocationOut(slug=location.slug, name=location.name) if location else None,
        flags=sorted(state.flags),
        ending=state.ending,
        npcs=[
            NpcRelationshipOut(slug=npc.slug, name=npc.name, trust=trust)
            for npc, trust in story_service.list_relationships(db, current_user.id)
        ],
    )


@router.post("/decision")
def story_decision():
    raise not_implemented("Story decisions")
