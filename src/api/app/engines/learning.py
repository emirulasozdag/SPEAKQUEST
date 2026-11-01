"""Learning Engine (adaptive learning).

Records categorized errors (Present Simple, Past Simple, Question Formation, Prepositions,
Vocabulary Usage) and the skill opportunities behind them, and turns those records into skill
scores, repeated mistakes and the next learning target. The rules and their numbers are explained
in docs/learning-engine.md; every threshold is a constant below.

The AI only detects mistakes; deciding what they mean for the player happens here, in Python.
Everything except record_message_analysis() is a pure function over values, so each rule can be
tested without a database. record_message_analysis() is the one place that writes language_errors
and skill_observations; services/learning.py loads the records for the read side.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy.orm import Session

from app.engines.categories import SkillCategory
from app.models.learning import LanguageError, ObservationResult, SkillObservation
from app.models.player import EnglishLevel

# --- Skill score (docs/learning-engine.md) ---------------------------------------------------
# Each opportunity's weight shrinks by this factor for every newer opportunity in the same
# category, so recent messages count most: the 5th newest weighs about half of the newest.
SCORE_DECAY = 0.85
# Before any opportunity a skill is unknown, not bad: it starts in the middle. The prior counts as
# this many opportunities, so one message moves the score but never to 0 or 100 at once.
PRIOR_SCORE = 50
PRIOR_WEIGHT = 2.0
# Score bands shown to the player
WEAK_BELOW = 50
STRONG_FROM = 75

# --- Repeated mistake ------------------------------------------------------------------------
# A category is a repeated mistake when at least REPEAT_MIN_MISTAKES of the player's last
# REPEAT_WINDOW_MESSAGES messages had a mistake in it. A message counts once, however many
# mistakes of that category it had.
REPEAT_WINDOW_MESSAGES = 10
REPEAT_MIN_MISTAKES = 3

# --- Learning target -------------------------------------------------------------------------
# A skill practised in the player's last few messages gets this many points added when ranking,
# so the next quest brings variety unless the skill is clearly the weakest.
RECENT_PRACTICE_MESSAGES = 3
RECENT_PRACTICE_PENALTY = 15
# Ties (and new players without data) follow a fixed order per level: the skills a learner at
# that level most needs first. Every category appears exactly once in each order.
LEVEL_ORDER: Mapping[EnglishLevel, tuple[SkillCategory, ...]] = {
    EnglishLevel.A2: (
        SkillCategory.PRESENT_SIMPLE,
        SkillCategory.VOCABULARY_USAGE,
        SkillCategory.QUESTION_FORMATION,
        SkillCategory.PREPOSITIONS,
        SkillCategory.PAST_SIMPLE,
    ),
    EnglishLevel.B1: (
        SkillCategory.PAST_SIMPLE,
        SkillCategory.QUESTION_FORMATION,
        SkillCategory.PREPOSITIONS,
        SkillCategory.PRESENT_SIMPLE,
        SkillCategory.VOCABULARY_USAGE,
    ),
}


@dataclass(frozen=True)
class DetectedMistake:
    category: SkillCategory
    original: str
    corrected: str
    explanation: str


def skill_observations(
    mistakes: Iterable[DetectedMistake], correctly_used: Iterable[SkillCategory]
) -> dict[SkillCategory, ObservationResult]:
    """One result per category the message touched.

    A category with any mistake counts as incorrect, even if the AI also lists it as correctly
    used ("She go to work and I drink coffee" is wrong and right Present Simple at once): one
    message is one opportunity, and a mistake in it is what the player needs to practise.
    """
    results = {SkillCategory(category): ObservationResult.CORRECT for category in correctly_used}
    for mistake in mistakes:
        results[SkillCategory(mistake.category)] = ObservationResult.INCORRECT
    return results


def record_message_analysis(
    db: Session,
    user_id: int,
    message_id: int,
    mistakes: Iterable[DetectedMistake],
    correctly_used: Iterable[SkillCategory],
) -> None:
    """Store the mistakes and skill opportunities of one player message. Does not commit: it runs
    inside the dialogue flow's transaction, so nothing is kept if a later step fails."""
    mistakes = list(mistakes)
    for mistake in mistakes:
        db.add(
            LanguageError(
                user_id=user_id,
                message_id=message_id,
                category=SkillCategory(mistake.category),
                original=mistake.original,
                corrected=mistake.corrected,
                explanation=mistake.explanation,
            )
        )
    for category, result in skill_observations(mistakes, correctly_used).items():
        db.add(SkillObservation(user_id=user_id, message_id=message_id, category=category, result=result))


# --- Read side: scores, repeated mistakes, learning target -----------------------------------


class SkillStatus(StrEnum):
    NOT_PRACTISED = "not_practised"
    WEAK = "weak"
    DEVELOPING = "developing"
    STRONG = "strong"


@dataclass(frozen=True)
class Observation:
    """One stored skill opportunity, as the engine sees it."""

    category: SkillCategory
    correct: bool
    message_id: int
    at: datetime | None = None


@dataclass(frozen=True)
class SkillScore:
    category: SkillCategory
    score: int
    status: SkillStatus
    opportunities: int
    correct_count: int
    error_count: int
    # Messages with a mistake in this category among the player's last REPEAT_WINDOW_MESSAGES
    recent_mistakes: int
    repeated: bool
    # Practised in the player's last RECENT_PRACTICE_MESSAGES messages
    practised_recently: bool
    last_practiced_at: datetime | None


class TargetReason(StrEnum):
    REPEATED_MISTAKE = "repeated_mistake"
    WEAKEST_SKILL = "weakest_skill"
    NOT_PRACTISED = "not_practised"
    REVIEW = "review"


@dataclass(frozen=True)
class LearningTarget:
    category: SkillCategory
    reason: TargetReason
    score: int


def skill_score(results: Sequence[bool]) -> int:
    """0-100 from one category's results, oldest first (True = used correctly).

    A weighted share of correct uses: the newest result has weight 1, each older one
    SCORE_DECAY times the next newer one. The prior (PRIOR_WEIGHT at PRIOR_SCORE) sits before the
    oldest result and fades the same way, so with enough practice the score can reach 0 or 100.
    """
    weight, weighted_correct, total_weight = 1.0, 0.0, 0.0
    for correct in reversed(results):
        weighted_correct += weight * correct
        total_weight += weight
        weight *= SCORE_DECAY
    prior = PRIOR_WEIGHT * weight
    share = (weighted_correct + prior * PRIOR_SCORE / 100) / (total_weight + prior)
    return round(share * 100)


def skill_status(score: int, opportunities: int) -> SkillStatus:
    if not opportunities:
        return SkillStatus.NOT_PRACTISED
    if score < WEAK_BELOW:
        return SkillStatus.WEAK
    if score < STRONG_FROM:
        return SkillStatus.DEVELOPING
    return SkillStatus.STRONG


def skill_scores(
    observations: Iterable[Observation], recent_message_ids: Sequence[int]
) -> dict[SkillCategory, SkillScore]:
    """A score for every category, in SkillCategory order.

    observations: all of the player's opportunities, oldest first. recent_message_ids: the
    player's own messages, newest first (at least REPEAT_WINDOW_MESSAGES of them when available);
    messages that touched no skill count too, since "the last 10 messages" means what the player
    actually wrote.
    """
    by_category: dict[SkillCategory, list[Observation]] = {category: [] for category in SkillCategory}
    for observation in observations:
        by_category[SkillCategory(observation.category)].append(observation)

    repeat_window = set(recent_message_ids[:REPEAT_WINDOW_MESSAGES])
    practice_window = set(recent_message_ids[:RECENT_PRACTICE_MESSAGES])
    scores = {}
    for category, items in by_category.items():
        score = skill_score([item.correct for item in items])
        recent_mistakes = len(
            {item.message_id for item in items if not item.correct and item.message_id in repeat_window}
        )
        scores[category] = SkillScore(
            category=category,
            score=score,
            status=skill_status(score, len(items)),
            opportunities=len(items),
            correct_count=sum(1 for item in items if item.correct),
            error_count=sum(1 for item in items if not item.correct),
            recent_mistakes=recent_mistakes,
            repeated=recent_mistakes >= REPEAT_MIN_MISTAKES,
            practised_recently=any(item.message_id in practice_window for item in items),
            last_practiced_at=items[-1].at if items else None,
        )
    return scores


def rank_learning_targets(scores: Mapping[SkillCategory, SkillScore], level: EnglishLevel) -> list[LearningTarget]:
    """Every category, best next target first. Deterministic: the same input always gives the
    same order.

    1. Repeated mistakes come first (more recent mistakes first).
    2. Then the lowest score, where a skill practised in the last few messages counts
       RECENT_PRACTICE_PENALTY points higher, so practice moves on unless a skill is clearly weak.
    3. Ties follow the level's order (LEVEL_ORDER).
    """
    order = LEVEL_ORDER[level]

    def key(item: SkillScore) -> tuple:
        penalty = RECENT_PRACTICE_PENALTY if item.practised_recently else 0
        return (
            not item.repeated,
            -item.recent_mistakes if item.repeated else 0,
            item.score + penalty,
            order.index(item.category),
        )

    return [
        LearningTarget(item.category, _reason(item), item.score) for item in sorted(scores.values(), key=key)
    ]


def choose_learning_target(scores: Mapping[SkillCategory, SkillScore], level: EnglishLevel) -> LearningTarget:
    """The one skill the next quest should practise (see rank_learning_targets)."""
    return rank_learning_targets(scores, level)[0]


def _reason(item: SkillScore) -> TargetReason:
    if item.repeated:
        return TargetReason.REPEATED_MISTAKE
    if not item.opportunities:
        return TargetReason.NOT_PRACTISED
    if item.score >= STRONG_FROM:
        return TargetReason.REVIEW
    return TargetReason.WEAKEST_SKILL


# --- Progress over time --------------------------------------------------------------------
# The most recent days with practice that the timeline keeps; older days are left out
TIMELINE_MAX_DAYS = 30


@dataclass(frozen=True)
class TimelinePoint:
    day: date
    # The score each category had at the end of that day; None until it was first practised
    scores: Mapping[SkillCategory, int | None]


def score_timeline(observations: Iterable[Observation]) -> list[TimelinePoint]:
    """Each category's score at the end of every day the player practised, oldest first.

    observations: all of the player's opportunities, oldest first. The score on a day uses every
    result up to and including that day, with the same formula as skill_score(), so the last point
    always equals the current score. Observations without a time are left out.
    """
    by_day: dict[date, list[Observation]] = {}
    for item in observations:
        if item.at is not None:
            at = item.at if item.at.tzinfo else item.at.replace(tzinfo=timezone.utc)
            by_day.setdefault(at.astimezone(timezone.utc).date(), []).append(item)

    results: dict[SkillCategory, list[bool]] = {category: [] for category in SkillCategory}
    points = []
    for day in sorted(by_day):
        for item in by_day[day]:
            results[SkillCategory(item.category)].append(item.correct)
        points.append(
            TimelinePoint(
                day=day,
                scores={category: skill_score(items) if items else None for category, items in results.items()},
            )
        )
    return points[-TIMELINE_MAX_DAYS:]
