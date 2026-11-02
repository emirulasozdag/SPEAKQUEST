"""Helpers for the browser smoke tests: a player prepared through the API, logging in, and the
fake NPC replies the tests use. The replies are the AI's JSON, checked by the backend as usual."""

import httpx
from playwright.sync_api import Page

from tests.ai_fakes import reply_json

PASSWORD = "a-long-secret"

# Meet Your Neighbor in two messages: the first has one present simple mistake and meets two goals,
# the second meets the last goal without mistakes
FIRST_MESSAGE = "Hi Alex, my name are Deniz. I am from Izmir."
FIRST_REPLY = reply_json(
    npc_reply="Nice to meet you, Deniz! Izmir is lovely. What do you usually do on weekdays?",
    detected_errors=[
        {
            "category": "present_simple",
            "original": "my name are Deniz",
            "corrected": "my name is Deniz",
            "explanation": "Tekil öznelerle 'is' kullanılır.",
        }
    ],
    correctly_used=[],
    feedback="Nice greeting! Remember: my name is.",
    suggested_story_action="npc_pleased",
    objectives_met=["greet", "introduce_yourself"],
)
SECOND_MESSAGE = "I walk to work every day."
SECOND_REPLY = reply_json(
    npc_reply="That sounds healthy! I take the bus, it is always full.",
    detected_errors=[],
    correctly_used=["present_simple"],
    feedback="Perfect sentence.",
    suggested_story_action="continue",
    objectives_met=["describe_routine"],
)


class GameApi:
    """Prepares a player through the same API the frontend calls, so a test starts where it needs to."""

    def __init__(self, base_url: str, email: str) -> None:
        self.http = httpx.Client(base_url=f"{base_url}/api", timeout=10)
        self.email = email
        self.headers: dict[str, str] = {}

    def call(self, method: str, path: str, **kwargs) -> httpx.Response:
        response = self.http.request(method, path, headers=self.headers, **kwargs)
        assert response.is_success, f"{method} {path} -> {response.status_code} {response.text}"
        return response

    def register_with_character(self, name: str = "Deniz", level: str = "A2") -> None:
        self.call("POST", "/auth/register", json={"email": self.email, "password": PASSWORD})
        token = self.call("POST", "/auth/login", json={"email": self.email, "password": PASSWORD}).json()
        self.headers = {"Authorization": f"Bearer {token['access_token']}"}
        character = {"character_name": name, "avatar": 1, "english_level": level, "learning_goal": "everyday"}
        self.call("PUT", "/player/profile", json=character)

    def quest(self, slug: str) -> dict:
        return next(quest for quest in self.call("GET", "/quests").json() if quest["slug"] == slug)

    def start(self, slug: str) -> dict:
        return self.call("POST", f"/quests/{self.quest(slug)['id']}/start").json()

    def say(self, message: str) -> dict:
        return self.call("POST", "/dialogue/message", json={"message": message}).json()

    def decide(self, slug: str, decision_id: str, option_id: str) -> None:
        body = {"quest_id": self.quest(slug)["id"], "decision_id": decision_id, "option_id": option_id}
        self.call("POST", "/story/decision", json=body)

    def complete(self, slug: str) -> dict:
        return self.call("POST", f"/quests/{self.quest(slug)['id']}/complete").json()


def log_in(page: Page, email: str, password: str = PASSWORD) -> None:
    """Logs in through the login page, the way a returning player does."""
    page.goto("/pages/login.html")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password", exact=True).fill(password)
    page.get_by_role("button", name="Log in").click()
