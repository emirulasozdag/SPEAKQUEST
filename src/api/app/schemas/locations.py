from pydantic import BaseModel

from app.services.quests import QuestStatus


class NpcOut(BaseModel):
    """What the player may see of a character. Personality, speaking style and what the NPC knows
    are prompt material and stay on the server (they can contain story spoilers)."""

    id: int
    slug: str
    name: str
    role: str


class LocationQuestOut(BaseModel):
    id: int
    slug: str
    title: str
    chapter: int
    summary: str
    npc_slug: str
    status: QuestStatus


class LocationOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str
    sort_order: int
    npcs: list[NpcOut]
    quests: list[LocationQuestOut]
