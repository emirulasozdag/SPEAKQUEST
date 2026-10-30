from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.placeholders import not_implemented
from app.models.user import User
from app.schemas.dialogue import DialogueHistoryOut, DialogueMessageOut
from app.services import dialogue as dialogue_service

router = APIRouter(prefix="/dialogue", tags=["dialogue"])


@router.post("/message")
def send_message():
    raise not_implemented("NPC dialogue")


@router.get("/history/{quest_id}", response_model=DialogueHistoryOut)
def dialogue_history(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DialogueHistoryOut:
    """The logged-in player's conversation for a quest they started, oldest first.

    404 when the quest is unknown or this player never started it, so another player's
    conversation is indistinguishable from one that does not exist.
    """
    try:
        messages = dialogue_service.get_history(db, current_user.id, quest_id)
    except dialogue_service.DialogueNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have not started this quest.") from None
    return DialogueHistoryOut(
        quest_id=quest_id, messages=[DialogueMessageOut.model_validate(message) for message in messages]
    )
