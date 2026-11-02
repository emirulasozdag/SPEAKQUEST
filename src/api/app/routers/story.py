from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.engines.learning import PRIOR_SCORE, most_improved_skill
from app.models.content import Npc
from app.models.user import User
from app.schemas.story import (
    DecisionOptionOut,
    DecisionOut,
    DecisionRequest,
    DecisionResultOut,
    EndingSummaryOut,
    ImprovedSkillOut,
    KeyDecisionOut,
    NpcRelationshipOut,
    StoryLocationOut,
    StoryStateOut,
)
from app.services import learning as learning_service
from app.services import players as player_service
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


@router.get("/ending", response_model=EndingSummaryOut)
def story_ending(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EndingSummaryOut:
    """The ending the player reached, with its summary, the decisions that led there, the XP
    earned and the skill that improved most; 404 while the story goes on."""
    ending = story_service.reached_ending(db, current_user.id)
    progress = player_service.get_progress(db, current_user.id)
    if ending is None or progress is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Your story has not ended yet.")
    improved = most_improved_skill(learning_service.get_skill_scores(db, current_user.id))
    return EndingSummaryOut(
        slug=ending.slug,
        title=ending.title,
        summary=ending.summary,
        xp=progress.profile.xp,
        level=progress.profile.level,
        quests_completed=progress.completed_quests,
        decisions=[
            KeyDecisionOut(quest_title=made.quest.title, prompt=made.point.prompt, choice=made.choice)
            for made in story_service.made_decisions(db, current_user.id)
        ],
        most_improved_skill=(
            ImprovedSkillOut(category=improved.category, start_score=PRIOR_SCORE, score=improved.score)
            if improved
            else None
        ),
    )


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
    already made or the quest is not started. The Story Engine applies its flags and trust; the
    quests a decision opens are reported when the quest is completed."""
    try:
        result = story_service.make_decision(
            db, current_user.id, payload.quest_id, payload.decision_id, payload.option_id
        )
    except story_service.DecisionRefusedError as refused:
        raise HTTPException(status_code=_REFUSAL_STATUS[refused.reason], detail=refused.message) from None

    names = dict(db.execute(select(Npc.slug, Npc.name).where(Npc.slug.in_(result.trust))).tuples().all())
    return DecisionResultOut(
        decision_id=payload.decision_id,
        option_id=payload.option_id,
        flags=sorted(result.flags),
        npcs=[NpcRelationshipOut(slug=slug, name=names[slug], trust=trust) for slug, trust in result.trust.items()],
    )
