from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.content import Npc
from app.models.user import User
from app.schemas.quests import EndingOut
from app.schemas.story import (
    DecisionOptionOut,
    DecisionOut,
    DecisionRequest,
    DecisionResultOut,
    NpcRelationshipOut,
    StoryLocationOut,
    StoryStateOut,
    UnlockedQuestOut,
)
from app.services import quests as quest_service
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


@router.get("/ending", response_model=EndingOut)
def story_ending(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EndingOut:
    """The ending the player reached, with its summary; 404 while the story goes on."""
    ending = story_service.reached_ending(db, current_user.id)
    if ending is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Your story has not ended yet.")
    return EndingOut(slug=ending.slug, title=ending.title, summary=ending.summary)


# not_started and already_made are about the order of play, not about a bad request
_REFUSAL_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "invalid": status.HTTP_400_BAD_REQUEST,
    "not_started": status.HTTP_409_CONFLICT,
    "already_made": status.HTTP_409_CONFLICT,
    "story_ended": status.HTTP_409_CONFLICT,
}


@router.get("/decisions/{quest_id}", response_model=list[DecisionOut])
def quest_decisions(
    quest_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DecisionOut]:
    """The decision points of a quest the player has started, with the options and what was chosen."""
    try:
        decisions = story_service.list_decisions(db, current_user.id, quest_id)
    except story_service.DecisionRefusedError as refused:
        raise HTTPException(status_code=_REFUSAL_STATUS[refused.reason], detail=refused.message) from None
    return [
        DecisionOut(
            id=item.point.id,
            prompt=item.point.prompt,
            options=[DecisionOptionOut(id=option.id, label=option.label) for option in item.point.options],
            chosen=item.chosen,
        )
        for item in decisions
    ]


@router.post("/decision", response_model=DecisionResultOut, status_code=status.HTTP_201_CREATED)
def story_decision(
    payload: DecisionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DecisionResultOut:
    """Make one of a started quest's decisions. 400 unknown decision or option, 409 when it was
    already made or the quest is not started. The Story Engine applies its flags and trust."""
    quests = quest_service.list_player_quests(db, current_user.id)
    locked_before = {item.quest.id for item in quests if item.status == quest_service.QuestStatus.LOCKED}
    try:
        result = story_service.make_decision(
            db, current_user.id, payload.quest_id, payload.decision_id, payload.option_id
        )
    except story_service.DecisionRefusedError as refused:
        raise HTTPException(status_code=_REFUSAL_STATUS[refused.reason], detail=refused.message) from None

    unlocked = [
        item.quest
        for item in quest_service.list_player_quests(db, current_user.id)
        if item.quest.id in locked_before and item.status != quest_service.QuestStatus.LOCKED
    ]
    names = dict(db.execute(select(Npc.slug, Npc.name).where(Npc.slug.in_(result.trust))).tuples().all())
    return DecisionResultOut(
        decision_id=payload.decision_id,
        option_id=payload.option_id,
        flags=sorted(result.flags),
        npcs=[NpcRelationshipOut(slug=slug, name=names[slug], trust=trust) for slug, trust in result.trust.items()],
        unlocked_quests=[UnlockedQuestOut(id=quest.id, slug=quest.slug, title=quest.title) for quest in unlocked],
    )
