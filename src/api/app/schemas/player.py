from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

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
