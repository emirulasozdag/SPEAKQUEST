from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.placeholders import not_implemented
from app.models.user import User
from app.schemas.quests import ActiveQuestOut, QuestSummaryOut
from app.services import quests as quest_service

router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("", response_model=list[QuestSummaryOut])
def list_quests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestSummaryOut]:
    """Every quest with the logged-in player's status for it."""
    return [QuestSummaryOut.from_player_quest(item) for item in quest_service.list_player_quests(db, current_user.id)]


@router.get("/active", response_model=ActiveQuestOut)
def active_quest(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActiveQuestOut:
    """The quest the player is playing now; 404 when there is none."""
    item = quest_service.get_active_quest(db, current_user.id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="You have no active quest.")
    return ActiveQuestOut.from_player_quest(item)


@router.post("/{quest_id}/start", response_model=ActiveQuestOut, status_code=status.HTTP_201_CREATED)
def start_quest(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ActiveQuestOut:
    """Start a quest. 404 unknown quest; 409 when it is locked, already started or another is active."""
    try:
        item = quest_service.start_quest(db, current_user.id, quest_id)
    except quest_service.QuestNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.") from None
    except quest_service.QuestStartRefusedError as refused:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=refused.message) from None
    return ActiveQuestOut.from_player_quest(item)


@router.post("/{quest_id}/complete")
def complete_quest(quest_id: int):
    raise not_implemented("Quest completion")
