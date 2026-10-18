"""SQLAlchemy models.

Each table from the data model (users, player_profiles, quests, ...) gets its own module here
and must be imported below, so Alembic can detect it when generating migrations.
"""

from app.core.database import Base

__all__ = ["Base"]
