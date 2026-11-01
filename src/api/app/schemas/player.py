from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

from app.engines.categories import SkillCategory
from app.engines.learning import SkillStatus
from app.engines.progression import progress_in_level
from app.models.player import AVATAR_COUNT, CHARACTER_NAME_MAX_LENGTH, EnglishLevel, LearningGoal

CharacterName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=CHARACTER_NAME_MAX_LENGTH)
]
# strict=True so values like "2" or true are rejected instead of being turned into a number
Avatar = Annotated[int, Field(strict=True, ge=1, le=AVATAR_COUNT)]


class ProfileUpdateRequest(BaseModel):
    # Unknown fields such as xp or level are rejected: only the backend changes them
    model_config = ConfigDict(extra="forbid")

    character_name: CharacterName
    avatar: Avatar
    english_level: EnglishLevel
    learning_goal: LearningGoal


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    character_name: str
    avatar: int
    english_level: EnglishLevel
    learning_goal: LearningGoal
    xp: int
    level: int
    created_at: datetime
    updated_at: datetime

    # For the XP bar: worked out by the progression rules, so the client never calculates levels
    @computed_field
    @property
    def xp_into_level(self) -> int:
        return progress_in_level(self.xp).xp_into_level

    @computed_field
    @property
    def xp_needed_for_next(self) -> int | None:
        """XP between this level and the next; None at the highest level."""
        return progress_in_level(self.xp).xp_needed_for_next


class WeakestSkillOut(BaseModel):
    category: SkillCategory
    # 0-100 from the Learning Engine (docs/learning-engine.md)
    score: int
    status: SkillStatus


class ProgressResponse(BaseModel):
    """A short summary of the player's progress, for the dashboard and the progress page."""

    level: int
    xp: int
    xp_into_level: int
    # None at the highest level
    xp_needed_for_next: int | None
    completed_quests: int
    total_quests: int
    # The latest quest start, quest completion or message; None before the first quest
    last_activity_at: datetime | None
    # The practised skill with the lowest score; None until the player has practised one
    weakest_skill: WeakestSkillOut | None
