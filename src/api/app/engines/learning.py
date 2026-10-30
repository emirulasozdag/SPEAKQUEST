"""Learning Engine (adaptive learning).

Records categorized errors (Present Simple, Past Simple, Question Formation, Prepositions,
Vocabulary Usage) and the skill opportunities behind them. Skill scores, repeated mistakes and the
next learning target are computed from these records in #16.

The AI only detects mistakes; deciding what they mean for the player happens here, in Python.
skill_observations() is a pure function; record_message_analysis() is the one place that writes
language_errors and skill_observations.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.engines.categories import SkillCategory
from app.models.learning import LanguageError, ObservationResult, SkillObservation


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
