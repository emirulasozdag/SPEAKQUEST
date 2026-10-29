"""SQLAlchemy models.

Each table from the data model (users, player_profiles, quests, ...) gets its own module here
and must be imported below, so Alembic can detect it when generating migrations.
"""

from app.core.database import Base
from app.models.content import Location, Npc, QuestTemplate
from app.models.player import PlayerProfile
from app.models.user import User

__all__ = ["Base", "Location", "Npc", "PlayerProfile", "QuestTemplate", "User"]
