"""Learning Engine: which skill opportunities one message produced."""

from app.engines.categories import SkillCategory
from app.engines.learning import DetectedMistake, skill_observations
from app.models.learning import ObservationResult


def mistake(category: SkillCategory) -> DetectedMistake:
    return DetectedMistake(category, "She go to work.", "She goes to work.", "Üçüncü tekil şahısta -s eklenir.")


def test_a_message_without_mistakes_or_correct_use_touches_no_skill():
    assert skill_observations([], []) == {}


def test_correct_use_counts_as_a_correct_opportunity():
    assert skill_observations([], [SkillCategory.PAST_SIMPLE]) == {SkillCategory.PAST_SIMPLE: ObservationResult.CORRECT}


def test_a_mistake_counts_as_an_incorrect_opportunity():
    assert skill_observations([mistake(SkillCategory.PREPOSITIONS)], []) == {
        SkillCategory.PREPOSITIONS: ObservationResult.INCORRECT
    }


def test_a_mistake_wins_over_correct_use_of_the_same_skill_in_one_message():
    results = skill_observations([mistake(SkillCategory.PRESENT_SIMPLE)], [SkillCategory.PRESENT_SIMPLE])

    assert results == {SkillCategory.PRESENT_SIMPLE: ObservationResult.INCORRECT}


def test_two_mistakes_in_one_skill_are_one_opportunity():
    results = skill_observations([mistake(SkillCategory.PAST_SIMPLE), mistake(SkillCategory.PAST_SIMPLE)], [])

    assert results == {SkillCategory.PAST_SIMPLE: ObservationResult.INCORRECT}


def test_each_skill_is_judged_on_its_own():
    results = skill_observations(
        [mistake(SkillCategory.PAST_SIMPLE)], [SkillCategory.QUESTION_FORMATION, SkillCategory.PAST_SIMPLE]
    )

    assert results == {
        SkillCategory.PAST_SIMPLE: ObservationResult.INCORRECT,
        SkillCategory.QUESTION_FORMATION: ObservationResult.CORRECT,
    }
