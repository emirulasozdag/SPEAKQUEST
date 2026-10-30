import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.routers.auth import login_limiter, register_limiter
from app.models import Base


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Rate limit counters are process-wide, so each test starts with empty ones."""
    login_limiter.clear()
    register_limiter.clear()
    yield
    login_limiter.clear()
    register_limiter.clear()


@pytest.fixture
def db_session():
    """A fresh in-memory SQLite database per test, so tests never touch PostgreSQL."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()
