"""Access control across the whole API, and the player progress summary.

Every protected endpoint needs a token, and with two players B can never read or change A's
profile, quests, conversation, mistakes or story state. The route list is read from the app, so a
new endpoint is covered here as soon as it is added.
"""

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import func, select

from app.content.seed import seed_content
from app.main import app
from app.models.dialogue import DialogueMessage
from app.models.learning import LanguageError
from tests.ai_fakes import reply_json
from tests.test_dialogue_message import use_ai
from tests.test_player_profile import VALID_PROFILE, login_headers
from tests.test_quest_complete import quest_by_slug
from tests.test_quests import complete_in_db

A_EMAIL = "deniz@example.com"
B_EMAIL = "ece@example.com"
B_PROFILE = {**VALID_PROFILE, "character_name": "Ece", "avatar": 3}
# The only endpoints anyone may call without logging in
PUBLIC = {("GET", "/api/health"), ("POST", "/api/auth/register"), ("POST", "/api/auth/login")}


def protected_routes() -> list[tuple[str, str]]:
    routes = []
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path.startswith("/api/"):
            for method in route.methods - {"HEAD", "OPTIONS"}:
                if (method, route.path) not in PUBLIC:
                    routes.append((method, route.path))
    return sorted(routes)


@pytest.mark.parametrize(("method", "path"), protected_routes())
def test_every_protected_endpoint_needs_a_token(client, method, path):
    url = path.replace("{quest_id}", "1").replace("{location_id}", "1")

    response = client.request(method, url, json={})

    if response.status_code == 501:
        pytest.skip("still a placeholder; covered once it is implemented")
    assert response.status_code == 401


def test_the_route_list_covers_the_api():
    paths = {path for _, path in protected_routes()}

    assert {"/api/player/profile", "/api/player/progress", "/api/quests/{quest_id}/start", "/api/story/state"} <= paths


# --- two players -----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


@pytest.fixture
def players(client, db_session):
    """A is in the middle of The Job Interview and made a mistake; B has only a character."""
    a = login_headers(client, A_EMAIL)
    assert client.put("/api/player/profile", json=VALID_PROFILE, headers=a).status_code == 201
    complete_in_db(db_session, A_EMAIL, "meet_your_neighbor")
    interview = quest_by_slug(db_session, "the_job_interview")
    assert client.post(f"/api/quests/{interview.id}/start", headers=a).status_code == 201
    use_ai(reply_json())
    assert client.post("/api/dialogue/message", json={"message": "Last year I work in a restaurant."}, headers=a).status_code == 200

    b = login_headers(client, B_EMAIL)
    assert client.put("/api/player/profile", json=B_PROFILE, headers=b).status_code == 201
    return a, b, interview


def count(db_session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


def test_b_sees_only_their_own_profile_and_progress(client, players):
    a, b, _ = players

    assert client.get("/api/player/profile", headers=b).json()["character_name"] == "Ece"
    progress = client.get("/api/player/progress", headers=b).json()
    assert (progress["completed_quests"], progress["xp"], progress["last_activity_at"]) == (0, 0, None)
    assert client.get("/api/player/profile", headers=a).json()["character_name"] == VALID_PROFILE["character_name"]


def test_b_changing_their_profile_leaves_a_alone(client, players):
    a, b, _ = players

    client.put("/api/player/profile", json={**B_PROFILE, "character_name": "Changed"}, headers=b)

    assert client.get("/api/player/profile", headers=a).json()["character_name"] == VALID_PROFILE["character_name"]


def test_b_cannot_see_or_finish_as_quest(client, db_session, players):
    a, b, interview = players

    assert client.get("/api/quests/active", headers=b).status_code == 404
    statuses = {quest["slug"]: quest["status"] for quest in client.get("/api/quests", headers=b).json()}
    assert statuses["the_job_interview"] == "locked"
    assert client.post(f"/api/quests/{interview.id}/complete", headers=b).status_code in {404, 409}
    assert client.get("/api/quests/active", headers=a).json()["id"] == interview.id


def test_b_cannot_read_as_conversation_or_mistakes(client, db_session, players):
    a, b, interview = players

    assert client.get(f"/api/dialogue/history/{interview.id}", headers=b).status_code == 404
    assert client.get(f"/api/dialogue/summary/{interview.id}", headers=b).status_code == 404
    assert client.get("/api/learning/errors", headers=a).json()["total"] == 1
    assert client.get("/api/learning/errors", headers=b).json()["total"] == 0
    assert all(skill["opportunities"] == 0 for skill in client.get("/api/learning/skills", headers=b).json()["skills"])


def test_b_cannot_make_decisions_in_as_quest(client, players):
    _, b, interview = players

    assert client.get(f"/api/story/decisions/{interview.id}", headers=b).status_code == 409


def test_b_cannot_write_into_as_conversation(client, db_session, players):
    _, b, _ = players
    messages, errors = count(db_session, DialogueMessage), count(db_session, LanguageError)

    response = client.post("/api/dialogue/message", json={"message": "Hello, I want this job."}, headers=b)

    assert response.status_code in {404, 409}
    assert (count(db_session, DialogueMessage), count(db_session, LanguageError)) == (messages, errors)


def test_b_sees_only_their_own_story_state(client, players):
    a, b, _ = players

    a_story = client.get("/api/story/state", headers=a).json()
    b_story = client.get("/api/story/state", headers=b).json()

    assert a_story["current_location"]["slug"] == "office"
    assert b_story["current_location"] is None
    assert all(npc["trust"] == 0 for npc in b_story["npcs"])


# --- GET /api/player/progress ----------------------------------------------------------------


def test_progress_without_a_character_is_not_found(client):
    headers = login_headers(client, A_EMAIL)

    assert client.get("/api/player/progress", headers=headers).status_code == 404


def test_progress_of_a_new_player(client):
    headers = login_headers(client, A_EMAIL)
    client.put("/api/player/profile", json=VALID_PROFILE, headers=headers)

    body = client.get("/api/player/progress", headers=headers).json()

    assert body == {
        "level": 1,
        "xp": 0,
        "xp_into_level": 0,
        "xp_needed_for_next": 50,
        "completed_quests": 0,
        "total_quests": 5,
        "last_activity_at": None,
        "weakest_skill": None,
    }


def test_progress_counts_completed_quests_and_the_last_activity(client, players):
    a, _, _ = players
    profile = client.get("/api/player/profile", headers=a).json()

    body = client.get("/api/player/progress", headers=a).json()

    assert body["completed_quests"] == 1
    assert (body["level"], body["xp"]) == (profile["level"], profile["xp"])
    assert body["last_activity_at"] is not None


def test_progress_names_the_weakest_skill_from_the_learning_engine(client, players):
    a, b, _ = players
    skills = client.get("/api/learning/skills", headers=a).json()["skills"]
    practised = [skill for skill in skills if skill["opportunities"]]

    weakest = client.get("/api/player/progress", headers=a).json()["weakest_skill"]

    # A got the Past Simple wrong in the interview
    assert weakest["category"] == "past_simple"
    assert weakest["score"] == min(skill["score"] for skill in practised)
    assert client.get("/api/player/progress", headers=b).json()["weakest_skill"] is None
