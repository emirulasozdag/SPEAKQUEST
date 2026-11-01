from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.engines.categories import SkillCategory
from app.models.player import EnglishLevel
from app.models.user import User
from app.schemas.learning import (
    LanguageErrorOut,
    LanguageErrorsOut,
    LearningTargetOut,
    RecommendationsOut,
    SkillScoreOut,
    SkillsOut,
)
from app.services import learning as learning_service
from app.services.players import get_profile

router = APIRouter(prefix="/learning", tags=["learning"])

MAX_ERRORS_PAGE = 100


@router.get("/errors", response_model=LanguageErrorsOut)
def language_errors(
    category: SkillCategory | None = None,
    limit: int = Query(20, ge=1, le=MAX_ERRORS_PAGE),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LanguageErrorsOut:
    """The logged-in player's mistakes, newest first, optionally of one category."""
    entries, total = learning_service.get_errors(db, current_user.id, category, limit, offset)
    return LanguageErrorsOut(
        errors=[
            LanguageErrorOut(
                id=entry.error.id,
                category=entry.error.category,
                original=entry.error.original,
                corrected=entry.error.corrected,
                explanation=entry.error.explanation,
                created_at=entry.error.created_at,
                quest_id=entry.quest_id,
                quest_title=entry.quest_title,
            )
            for entry in entries
        ],
        total=total,
    )


@router.get("/skills", response_model=SkillsOut)
def skills(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SkillsOut:
    """A 0-100 score for every skill and the skills with a repeated mistake.

    A new player gets every skill at the starting score with status "not_practised".
    """
    scores = learning_service.get_skill_scores(db, current_user.id)
    repeated = sorted((s for s in scores.values() if s.repeated), key=lambda s: -s.recent_mistakes)
    return SkillsOut(
        skills=[SkillScoreOut.from_score(score) for score in scores.values()],
        repeated_mistakes=[s.category for s in repeated],
    )


@router.get("/recommendations", response_model=RecommendationsOut)
def recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecommendationsOut:
    """The skill the next quest should practise, and why. 404 without a character, because the
    choice depends on the player's English level."""
    profile = get_profile(db, current_user.id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Create your character first.")
    ranking = learning_service.get_learning_targets(db, current_user.id, EnglishLevel(profile.english_level))
    out = [LearningTargetOut.from_target(target) for target in ranking]
    return RecommendationsOut(target=out[0], ranking=out)
