import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.main import app
from app.routers.auth import login_limiter, register_limiter
from app.models import Base
from app.services.ai.client import get_ai_client


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Rate limit counters are process-wide, so each test starts with empty ones."""
    login_limiter.clear()
    register_limiter.clear()
    yield
    login_limiter.clear()
    register_limiter.clear()


# Set to a PostgreSQL URL (an empty database used only for tests) to run the tests there instead of
# SQLite, as the CI's PostgreSQL job does. Every table in it is dropped and created again per test.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


@pytest.fixture
def db_session():
    """A fresh database per test: in-memory SQLite by default, PostgreSQL with TEST_DATABASE_URL."""
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(engine)
    else:
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
        if TEST_DATABASE_URL:
            Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    # No test ever calls a real AI provider through the API; dialogue tests set their own fake
    app.dependency_overrides[get_ai_client] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()
