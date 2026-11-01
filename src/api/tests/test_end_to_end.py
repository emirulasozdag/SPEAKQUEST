"""One player's whole journey through the real API, end to end (#19).

Only the AI provider is faked; every other step goes through the same endpoints the frontend
calls, in the order a player meets them: register -> log in -> create a character -> pick a quest
-> talk to the NPC -> make a story decision -> complete the quest -> see the learning results and
the progress -> start the next quest.
"""

import pytest

from app.content.seed import seed_content
from tests.ai_fakes import reply_json
from tests.test_dialogue_message import use_ai

EMAIL = "journey@example.com"
PASSWORD = "a-long-secret"
CHARACTER = {"character_name": "Deniz", "avatar": 1, "english_level": "A2", "learning_goal": "everyday"}


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


def quests_by_slug(client, headers) -> dict[str, dict]:
    return {quest["slug"]: quest for quest in client.get("/api/quests", headers=headers).json()}


def test_a_player_goes_from_registration_to_the_next_quest(client):
    # 1. Account and login
    assert client.post("/api/auth/register", json={"email": EMAIL, "password": PASSWORD}).status_code == 201
    login = client.post("/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # 2. Without a character the game cannot start; with one it can
    assert client.get("/api/player/profile", headers=headers).status_code == 404
    assert client.put("/api/player/profile", json=CHARACTER, headers=headers).status_code == 201
    assert client.get("/api/learning/recommendations", headers=headers).json()["target"]["category"] == "present_simple"

    # 3. Only the first quest is open; the others wait for it
    quests = quests_by_slug(client, headers)
    assert quests["meet_your_neighbor"]["status"] == "available"
    assert {quests[slug]["status"] for slug in quests if slug != "meet_your_neighbor"} == {"locked"}
    assert client.get("/api/quests/active", headers=headers).status_code == 404

    # 4. Start it: the NPC opens the conversation
    first = quests["meet_your_neighbor"]
    started = client.post(f"/api/quests/{first['id']}/start", headers=headers)
    assert started.status_code == 201
    history = client.get(f"/api/dialogue/history/{first['id']}", headers=headers).json()["messages"]
    assert [m["role"] for m in history] == ["npc"]
    # Completing before the goals are met is refused
    assert client.post(f"/api/quests/{first['id']}/complete", headers=headers).status_code == 409

    # 5. Talk: one mistake, then the remaining goals; the backend checks every claim
    use_ai(
        reply_json(
            detected_errors=[
                {
                    "category": "present_simple",
                    "original": "my name are Deniz",
                    "corrected": "my name is Deniz",
                    "explanation": "Tekil öznelerle 'is' kullanılır.",
                }
            ],
            correctly_used=[],
            objectives_met=["greet", "introduce_yourself"],
            suggested_story_action="npc_pleased",
        ),
        reply_json(detected_errors=[], correctly_used=["present_simple"], objectives_met=["describe_routine"]),
    )
    turn = client.post("/api/dialogue/message", json={"message": "Hi Alex, my name are Deniz."}, headers=headers)
    assert turn.status_code == 200
    assert turn.json()["newly_met"] == ["greet", "introduce_yourself"]
    turn = client.post("/api/dialogue/message", json={"message": "I walk to work every day."}, headers=headers)
    assert all(goal["met"] for goal in turn.json()["objectives"])

    # 6. A story decision opens a quest that needs it
    decision = client.post(
        "/api/story/decision",
        json={"quest_id": first["id"], "decision_id": "help_alex_move", "option_id": "help"},
        headers=headers,
    )
    assert decision.status_code == 201
    assert "helped_alex" in decision.json()["flags"]

    # 7. Complete: XP once, and the next quests open
    done = client.post(f"/api/quests/{first['id']}/complete", headers=headers)
    assert done.status_code == 200
    assert (done.json()["xp_gained"], done.json()["xp"], done.json()["level"]) == (50, 50, 2)
    assert client.post(f"/api/quests/{first['id']}/complete", headers=headers).status_code == 409
    quests = quests_by_slug(client, headers)
    assert quests["meet_your_neighbor"]["status"] == "completed"
    assert {quests[slug]["status"] for slug in ("morning_at_the_cafe", "the_flat_viewing", "the_job_interview")} == {
        "available"
    }
    assert quests["the_missing_backpack"]["status"] == "locked"

    # 8. What the conversation taught: the mistake, the skill, the summary and the progress
    errors = client.get("/api/learning/errors", headers=headers).json()
    assert errors["total"] == 1
    assert errors["errors"][0]["quest_title"] == first["title"]
    skills = {s["category"]: s for s in client.get("/api/learning/skills", headers=headers).json()["skills"]}
    assert (skills["present_simple"]["opportunities"], skills["present_simple"]["error_count"]) == (2, 1)
    summary = client.get(f"/api/dialogue/summary/{first['id']}", headers=headers).json()
    assert (summary["messages_sent"], summary["understood"], summary["mistakes"]) == (2, 2, 1)
    progress = client.get("/api/player/progress", headers=headers).json()
    assert (progress["level"], progress["xp"], progress["completed_quests"]) == (2, 50, 1)
    assert progress["weakest_skill"]["category"] == "present_simple"

    # 9. The next quest starts with a fresh conversation
    nxt = quests["morning_at_the_cafe"]
    assert client.post(f"/api/quests/{nxt['id']}/start", headers=headers).status_code == 201
    active = client.get("/api/quests/active", headers=headers).json()
    assert active["slug"] == "morning_at_the_cafe"
    assert not any(goal["met"] for goal in active["objectives"])
    assert len(client.get(f"/api/dialogue/history/{nxt['id']}", headers=headers).json()["messages"]) == 1
