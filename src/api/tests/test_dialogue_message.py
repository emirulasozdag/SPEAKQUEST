"""POST /api/dialogue/message: one dialogue turn, with a fake AI client (never a real provider)."""

import pytest
from sqlalchemy import func, select

from app.content.seed import seed_content
from app.engines.story import ACTION_TRUST_STEP
from app.main import app
from app.models.dialogue import DialogueMessage
from app.models.learning import LanguageError, SkillObservation
from app.models.quest_progress import QuestProgress
from app.models.story import NpcRelationship
from app.models.user import User
from app.services.ai.analysis import FALLBACK_NPC_REPLY
from app.services.ai.client import AiError, get_ai_client
from tests.ai_fakes import VALID_REPLY, FakeAiClient, reply_json
from tests.test_player_profile import VALID_PROFILE, login_headers
from tests.test_quest_complete import quest_by_slug
from tests.test_quests import complete_in_db

MESSAGE_URL = "/api/dialogue/message"
EMAIL = "deniz@example.com"
README_EXAMPLE = "Last year I work in a restaurant."


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


@pytest.fixture
def headers(client) -> dict[str, str]:
    headers = login_headers(client, EMAIL)
    assert client.put("/api/player/profile", json=VALID_PROFILE, headers=headers).status_code == 201
    return headers


def use_ai(*replies) -> FakeAiClient:
    fake = FakeAiClient(*replies)
    app.dependency_overrides[get_ai_client] = lambda: fake
    return fake


@pytest.fixture
def interview(client, headers, db_session):
    """The Job Interview is active: the README example comes from this quest."""
    complete_in_db(db_session, EMAIL, "meet_your_neighbor")
    quest = quest_by_slug(db_session, "the_job_interview")
    assert client.post(f"/api/quests/{quest.id}/start", headers=headers).status_code == 201
    return quest


def send(client, headers, message: str):
    return client.post(MESSAGE_URL, json={"message": message}, headers=headers)


def count(db_session, model) -> int:
    return db_session.scalar(select(func.count()).select_from(model))


def user_id(db_session) -> int:
    return db_session.scalar(select(User.id).where(User.email == EMAIL))


# --- the happy path --------------------------------------------------------------------------


def test_the_readme_example_gets_a_reply_a_correction_and_counts_as_understood(client, headers, interview, db_session):
    use_ai(reply_json())

    response = send(client, headers, README_EXAMPLE)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["quest_id"] == interview.id
    assert body["npc_reply"] == VALID_REPLY["npc_reply"]
    assert body["communication_success"] is True
    assert body["corrections"] == [
        {
            "category": "past_simple",
            "original": README_EXAMPLE,
            "corrected": "Last year I worked in a restaurant.",
            "explanation": VALID_REPLY["detected_errors"][0]["explanation"],
        }
    ]
    assert body["feedback"] == VALID_REPLY["feedback"]
    assert body["player_message"]["text"] == README_EXAMPLE
    assert body["player_message"]["communication_success"] is True
    assert body["npc_message"]["text"] == VALID_REPLY["npc_reply"]


def test_both_messages_are_stored_after_the_opening_line(client, headers, interview):
    use_ai(reply_json())
    send(client, headers, README_EXAMPLE)

    messages = client.get(f"/api/dialogue/history/{interview.id}", headers=headers).json()["messages"]

    assert [(m["role"], m["text"]) for m in messages] == [
        ("npc", interview.npc_opening),
        ("player", README_EXAMPLE),
        ("npc", VALID_REPLY["npc_reply"]),
    ]


def test_mistakes_are_recorded_by_the_learning_engine(client, headers, interview, db_session):
    use_ai(reply_json())

    body = send(client, headers, README_EXAMPLE).json()

    [error] = db_session.scalars(select(LanguageError)).all()
    assert error.user_id == user_id(db_session)
    assert error.message_id == body["player_message"]["id"]
    assert (error.category, error.original, error.corrected) == (
        "past_simple",
        README_EXAMPLE,
        "Last year I worked in a restaurant.",
    )
    assert error.explanation
    assert error.created_at is not None
    [observation] = db_session.scalars(select(SkillObservation)).all()
    assert (observation.category, observation.result) == ("past_simple", "incorrect")


def test_correct_use_is_recorded_as_a_skill_opportunity(client, headers, interview, db_session):
    use_ai(reply_json(detected_errors=[], correctly_used=["past_simple", "present_simple"]))

    body = send(client, headers, "Last year I worked in a restaurant and I like people.").json()

    assert body["corrections"] == []
    assert count(db_session, LanguageError) == 0
    results = {o.category: o.result for o in db_session.scalars(select(SkillObservation))}
    assert results == {"past_simple": "correct", "present_simple": "correct"}


def test_an_allowed_story_action_goes_through_the_story_engine(client, headers, interview, db_session):
    use_ai(reply_json(suggested_story_action="interview_positive"))

    body = send(client, headers, README_EXAMPLE).json()

    assert body["story_action"] == {"suggested": "interview_positive", "accepted": True}
    trust = client.get("/api/story/state", headers=headers).json()["npcs"]
    assert {n["slug"]: n["trust"] for n in trust}["olivia"] == ACTION_TRUST_STEP


def test_a_story_action_the_quest_does_not_allow_is_refused(client, headers, interview, db_session):
    use_ai(reply_json(suggested_story_action="clue_found"))

    body = send(client, headers, README_EXAMPLE).json()

    assert body["story_action"] == {"suggested": "clue_found", "accepted": False}
    assert count(db_session, NpcRelationship) == 0


def test_a_misunderstood_message_is_stored_as_not_understood(client, headers, interview, db_session):
    use_ai(reply_json(communication_success=False, detected_errors=[], suggested_story_action="npc_confused"))

    body = send(client, headers, "banana window yesterday").json()

    assert body["communication_success"] is False
    assert body["player_message"]["communication_success"] is False


def test_the_message_does_not_mark_quest_objectives(client, headers, interview, db_session):
    """Objectives are marked per message in #31; this flow must not touch them."""
    use_ai(reply_json())

    send(client, headers, README_EXAMPLE)

    assert db_session.scalar(select(QuestProgress.objectives_met).where(QuestProgress.status == "active")) == []


def test_the_message_is_trimmed_before_it_is_stored(client, headers, interview):
    use_ai(reply_json())

    body = send(client, headers, f"   {README_EXAMPLE}  \n").json()

    assert body["player_message"]["text"] == README_EXAMPLE


# --- what reaches the AI ---------------------------------------------------------------------


def test_the_prompt_has_the_scene_the_history_and_the_message_but_nothing_private(client, headers, interview):
    fake = use_ai(reply_json(), reply_json())
    send(client, headers, "Hello, I am Deniz.")
    send(client, headers, README_EXAMPLE)

    system, user = fake.calls[-1]

    assert "Olivia" in system
    assert interview.title in system
    assert "interview_positive" in system
    assert "Chapter" in system
    assert interview.npc_opening in user
    assert "Hello, I am Deniz." in user
    assert f"<player_message>\n{README_EXAMPLE}\n</player_message>" in user
    assert EMAIL not in system + user


# --- refusals --------------------------------------------------------------------------------


def test_sending_requires_a_token(client):
    assert client.post(MESSAGE_URL, json={"message": "Hi"}).status_code == 401


@pytest.mark.parametrize("message", ["", "   ", "\n\t"])
def test_an_empty_message_is_refused(client, headers, interview, message):
    fake = use_ai()

    response = send(client, headers, message)

    assert response.status_code == 422
    assert response.json()["detail"] == "Write a message first."
    assert fake.calls == []


def test_a_message_over_500_characters_is_refused_and_500_is_fine(client, headers, interview):
    fake = use_ai(reply_json())

    too_long = send(client, headers, "a" * 501)
    just_right = send(client, headers, "a" * 500)

    assert too_long.status_code == 422
    assert too_long.json()["detail"] == "Keep your message under 500 characters."
    assert just_right.status_code == 200
    assert len(fake.calls) == 1


def test_without_an_active_quest_there_is_no_one_to_talk_to(client, headers):
    fake = use_ai()

    response = send(client, headers, "Hello?")

    assert response.status_code == 409
    assert response.json()["detail"] == "Start a quest before talking to someone."
    assert fake.calls == []


def test_without_a_character_the_player_cannot_talk(client):
    headers = login_headers(client, "ece@example.com")

    response = send(client, headers, "Hello?")

    assert response.status_code == 409
    assert response.json()["detail"] == "Create your character first."


def test_a_missing_message_field_is_a_validation_error(client, headers):
    assert client.post(MESSAGE_URL, json={}, headers=headers).status_code == 422


# --- when the AI fails, nothing changes ------------------------------------------------------


def assert_nothing_changed(db_session, messages_before: int) -> None:
    assert count(db_session, DialogueMessage) == messages_before
    assert count(db_session, LanguageError) == 0
    assert count(db_session, SkillObservation) == 0
    assert count(db_session, NpcRelationship) == 0


@pytest.mark.parametrize(
    "replies",
    [
        (AiError("timeout"),),
        (AiError("auth"),),
        ("not json at all", "still not json"),
        (reply_json(communication_success="yes"), reply_json(communication_success="yes")),
    ],
    ids=["timeout", "auth", "invalid_json", "invalid_schema"],
)
def test_an_ai_failure_gives_the_fallback_reply_and_stores_nothing(client, headers, interview, db_session, replies):
    use_ai(*replies)
    before = count(db_session, DialogueMessage)

    response = send(client, headers, README_EXAMPLE)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ai_unavailable"
    assert body["npc_reply"] == FALLBACK_NPC_REPLY
    assert body["communication_success"] is None
    assert body["corrections"] == []
    assert body["player_message"] is None
    assert_nothing_changed(db_session, before)


def test_without_a_configured_provider_the_game_still_answers(client, headers, interview, db_session):
    # conftest's default: get_ai_client returns None, as when AI_PROVIDER is empty
    before = count(db_session, DialogueMessage)

    body = send(client, headers, README_EXAMPLE).json()

    assert body["status"] == "ai_unavailable"
    assert body["npc_reply"] == FALLBACK_NPC_REPLY
    assert_nothing_changed(db_session, before)


def test_after_a_failure_the_same_message_can_be_sent_again(client, headers, interview, db_session):
    use_ai(AiError("unavailable"), AiError("unavailable"))
    assert send(client, headers, README_EXAMPLE).json()["status"] == "ai_unavailable"

    use_ai(reply_json())
    assert send(client, headers, README_EXAMPLE).json()["status"] == "ok"

    assert count(db_session, DialogueMessage) == 3


# --- players do not see each other -----------------------------------------------------------


def test_messages_go_to_the_senders_own_quest_only(client, headers, interview, db_session):
    other = login_headers(client, "ece@example.com")
    client.put("/api/player/profile", json=VALID_PROFILE, headers=other)
    starter = quest_by_slug(db_session, "meet_your_neighbor")
    # Ece's active quest is a different one; Deniz's message must not land there
    client.post(f"/api/quests/{starter.id}/start", headers=other)
    use_ai(reply_json())

    send(client, headers, README_EXAMPLE)

    ece_history = client.get(f"/api/dialogue/history/{starter.id}", headers=other).json()["messages"]
    assert [m["role"] for m in ece_history] == ["npc"]
    ece_id = db_session.scalar(select(User.id).where(User.email == "ece@example.com"))
    assert db_session.scalar(select(func.count()).select_from(LanguageError).where(LanguageError.user_id == ece_id)) == 0
