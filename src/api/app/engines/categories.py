"""Language skill categories, shared by quest content, the AI response schema and the
Learning Engine. A category added here becomes valid everywhere."""

from enum import StrEnum


class SkillCategory(StrEnum):
    PRESENT_SIMPLE = "present_simple"
    PAST_SIMPLE = "past_simple"
    QUESTION_FORMATION = "question_formation"
    PREPOSITIONS = "prepositions"
    VOCABULARY_USAGE = "vocabulary_usage"
