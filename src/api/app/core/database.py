"""SQLAlchemy engine, session factory and the declarative base shared by all models."""

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 3},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Parent class for every SQLAlchemy model in app/models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that opens a session per request and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_is_reachable() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
