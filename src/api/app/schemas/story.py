from pydantic import BaseModel, ConfigDict, Field

from app.engines.categories import SkillCategory
from app.schemas.quests import EndingOut


class StoryLocationOut(BaseModel):
    slug: str
    name: str


class NpcRelationshipOut(BaseModel):
    slug: str
    name: str
    # 0-100; an NPC the player has not won over yet is 0
    trust: int


class StoryStateOut(BaseModel):
    chapter: int
    current_location: StoryLocationOut | None
    flags: list[str]
    ending: str | None
    npcs: list[NpcRelationshipOut]


class DecisionOptionOut(BaseModel):
    """An option as the player sees it. Its effects (flags, trust) stay on the server."""

    id: str
    label: str


class DecisionOut(BaseModel):
    id: str
    prompt: str
    options: list[DecisionOptionOut]
    # The option the player chose; null while the decision is still open
    chosen: str | None


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quest_id: int
    decision_id: str = Field(min_length=1, max_length=60)
    option_id: str = Field(min_length=1, max_length=60)


class DecisionResultOut(BaseModel):
    decision_id: str
    option_id: str
    flags: list[str]
    # Only the NPCs whose trust this decision changed
    npcs: list[NpcRelationshipOut]


class KeyDecisionOut(BaseModel):
    quest_title: str
    prompt: str
    # The label of the option the player chose
    choice: str


class ImprovedSkillOut(BaseModel):
    category: SkillCategory
    # Where every skill starts and where this one is now, both 0-100
    start_score: int
    score: int


class EndingSummaryOut(EndingOut):
    """The ending with what the player's story added up to. Every value is the backend's own."""

    xp: int
    level: int
    quests_completed: int
    decisions: list[KeyDecisionOut]
    # The skill that rose furthest above its starting score; null when none rose
    most_improved_skill: ImprovedSkillOut | None
