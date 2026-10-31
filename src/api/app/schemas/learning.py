from datetime import datetime

from pydantic import BaseModel

from app.engines.categories import SkillCategory
from app.engines.learning import LearningTarget, SkillScore, SkillStatus, TargetReason

# What each target reason means, in the player's words. The engine only returns the code. The
# sentences describe the skill itself, so they stay true for every place in the ranking, not only
# for the first one.
REASON_MESSAGES = {
    TargetReason.REPEATED_MISTAKE: "You made this mistake several times in your last messages.",
    TargetReason.WEAKEST_SKILL: "This skill needs more practice.",
    TargetReason.NOT_PRACTISED: "You have not practised this skill yet.",
    TargetReason.REVIEW: "This skill looks strong. A quick review keeps it fresh.",
}


class SkillScoreOut(BaseModel):
    category: SkillCategory
    # 0-100, see docs/learning-engine.md
    score: int
    status: SkillStatus
    opportunities: int
    correct_count: int
    error_count: int
    recent_mistakes: int
    repeated: bool
    last_practiced_at: datetime | None

    @classmethod
    def from_score(cls, item: SkillScore) -> "SkillScoreOut":
        return cls(
            category=item.category,
            score=item.score,
            status=item.status,
            opportunities=item.opportunities,
            correct_count=item.correct_count,
            error_count=item.error_count,
            recent_mistakes=item.recent_mistakes,
            repeated=item.repeated,
            last_practiced_at=item.last_practiced_at,
        )


class SkillsOut(BaseModel):
    skills: list[SkillScoreOut]
    # Categories with a repeated mistake, the most recent mistakes first
    repeated_mistakes: list[SkillCategory]


class LearningTargetOut(BaseModel):
    category: SkillCategory
    reason: TargetReason
    message: str
    score: int

    @classmethod
    def from_target(cls, target: LearningTarget) -> "LearningTargetOut":
        return cls(
            category=target.category,
            reason=target.reason,
            message=REASON_MESSAGES[target.reason],
            score=target.score,
        )


class RecommendationsOut(BaseModel):
    # The skill the next quest should practise
    target: LearningTargetOut
    # Every skill in the engine's order; the first one is the target
    ranking: list[LearningTargetOut]


class LanguageErrorOut(BaseModel):
    id: int
    category: SkillCategory
    original: str
    corrected: str
    # One short sentence in Turkish
    explanation: str
    created_at: datetime
    quest_id: int
    quest_title: str


class LanguageErrorsOut(BaseModel):
    errors: list[LanguageErrorOut]
    # All matching mistakes, for paging
    total: int
