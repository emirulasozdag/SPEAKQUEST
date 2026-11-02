"""A live server and a real browser for the smoke tests (#63).

The app runs with uvicorn in a background thread on a free port. Each test gets an empty test
database with the game content seeded, and a fake AI client: the real AI is never called.
Every test also fails on a JavaScript error, an unexpected console error or a 5xx answer.
"""

import os
import socket
import threading
import time

import pytest
import uvicorn
from playwright.sync_api import Page
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.content.seed import seed_content
from app.core.database import get_db
from app.main import app
from app.models import Base
from app.routers import health
from app.services.ai.client import get_ai_client
from tests.ai_fakes import FakeAiClient
from tests.browser.game import GameApi

# The same switch as tests/conftest.py: an empty PostgreSQL database instead of SQLite
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="session")
def live_server():
    """The whole app (API and frontend) on http://127.0.0.1:<port>, for the whole test session."""
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started:
        if time.monotonic() > deadline or not thread.is_alive():
            raise RuntimeError("The test server did not start")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture(scope="session")
def base_url(live_server):
    """pytest-playwright opens relative URLs (page.goto("/pages/login.html")) on the live server."""
    return live_server


@pytest.fixture(autouse=True)
def browser_database(tmp_path, monkeypatch):
    """A fresh database per test: a SQLite file by default, PostgreSQL with TEST_DATABASE_URL."""
    if TEST_DATABASE_URL:
        engine = create_engine(TEST_DATABASE_URL)
        Base.metadata.drop_all(engine)
    else:
        # A file, not memory: the server answers requests from several threads at once
        engine = create_engine(f"sqlite:///{tmp_path / 'browser.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with Session() as db:
        seed_content(db)

    def get_test_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def reachable() -> bool:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True

    app.dependency_overrides[get_db] = get_test_db
    # Until a test hands out replies, a message to the NPC fails the test instead of calling an AI
    app.dependency_overrides[get_ai_client] = lambda: FakeAiClient()
    # The status badge in the navbar asks /api/health about the test database, not the real one
    monkeypatch.setattr(health, "database_is_reachable", reachable)
    yield engine
    app.dependency_overrides.clear()
    if TEST_DATABASE_URL:
        Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def use_ai():
    """use_ai(reply, reply, ...): the NPC answers the next messages with these replies, in order."""

    def install(*replies: str) -> FakeAiClient:
        fake = FakeAiClient(*replies)
        app.dependency_overrides[get_ai_client] = lambda: fake
        return fake

    return install


class Console:
    """What went wrong in the browser while a test ran."""

    def __init__(self) -> None:
        self.errors: list[str] = []

    def watch(self, page: Page) -> None:
        page.on("pageerror", lambda error: self.errors.append(f"JavaScript error: {error}"))
        page.on("console", self._on_console)
        page.on("response", self._on_response)

    def _on_console(self, message) -> None:
        if message.type != "error":
            return
        # The API answers some requests with 4xx on purpose (no active quest yet: 404) and the page
        # handles it; the browser still logs the status. Any other console error counts.
        url = message.location.get("url", "")
        if message.text.startswith("Failed to load resource") and "/api/" in url:
            return
        self.errors.append(f"Console error: {message.text} ({url})")

    def _on_response(self, response) -> None:
        if response.status >= 500:
            self.errors.append(f"Server error {response.status}: {response.request.method} {response.url}")


@pytest.fixture
def console(page: Page) -> Console:
    """Each test ends with `assert console.errors == []`."""
    watcher = Console()
    watcher.watch(page)
    return watcher


@pytest.fixture
def game_api(live_server):
    api = GameApi(live_server, "player@example.com")
    yield api
    api.http.close()
