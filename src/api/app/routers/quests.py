from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.quests import ActiveQuestOut, QuestCompletedOut, QuestListItemOut, QuestSummaryOut
from app.services import quests as quest_service

router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("", response_model=list[QuestListItemOut])
def list_quests(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestListItemOut]:
    """Every quest with the logged-in player's status for it. The quest the Adaptive Quest Engine
    recommends next is marked, with the reason; none is marked while a quest is active. Locked
    quests say what they are still waiting for."""
    recommendation = quest_service.recommend_quest(db, current_user.id)
    quests = quest_service.list_player_quests(db, current_user.id)
    locked = quest_service.lock_reasons(db, current_user.id, quests)
    items = []
    for item in quests:
        recommended = recommendation is not None and item.quest.slug == recommendation.slug
        items.append(
            QuestListItemOut(
                **QuestSummaryOut.from_player_quest(item).model_dump(),
                recommended=recommended,
                recommendation_reason=recommendation.reason if recommended else None,
                locked_reason=locked.get(item.quest.slug),
            )
        )
    return items


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


@router.post("/{quest_id}/complete", response_model=QuestCompletedOut)
def complete_quest(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestCompletedOut:
    """Complete the active quest once its objectives are met and pay its XP.

    404 unknown quest; 409 when it was not started, is already completed, still has unmet
    objectives or the player has no character yet.
    """
    try:
        completed = quest_service.complete_quest(db, current_user.id, quest_id)
    except quest_service.QuestNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quest not found.") from None
    except quest_service.QuestCompleteRefusedError as refused:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=refused.message) from None
    return QuestCompletedOut.from_completed(completed)
