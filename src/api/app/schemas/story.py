from pydantic import BaseModel


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
