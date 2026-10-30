"""GET /api/dialogue/history/{quest_id}: a player reads back only their own conversation."""

import pytest
from sqlalchemy import func, select

from app.content.seed import seed_content
from app.models.content import QuestTemplate
from app.models.dialogue import DialogueMessage
from app.models.quest_progress import QuestProgress
from app.models.user import User
from tests.test_player_profile import login_headers

HISTORY_URL = "/api/dialogue/history"
STARTER = "meet_your_neighbor"


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


@pytest.fixture
def headers(client) -> dict[str, str]:
    return login_headers(client, "deniz@example.com")


def starter(db_session) -> QuestTemplate:
    return db_session.scalar(select(QuestTemplate).where(QuestTemplate.slug == STARTER))


def start_starter(client, headers, db_session) -> QuestTemplate:
    quest = starter(db_session)
    assert client.post(f"/api/quests/{quest.id}/start", headers=headers).status_code == 201
    return quest


def add_messages(db_session, email: str, quest: QuestTemplate, *lines: tuple[str, str, bool | None]) -> None:
    """Store messages the way the dialogue endpoint (#12) will: (role, text, communication_success)."""
    user_id = db_session.scalar(select(User.id).where(User.email == email))
    progress_id = db_session.scalar(
        select(QuestProgress.id).where(QuestProgress.user_id == user_id, QuestProgress.quest_template_id == quest.id)
    )
    for role, text, success in lines:
        db_session.add(
            DialogueMessage(quest_progress_id=progress_id, role=role, text=text, communication_success=success)
        )
    db_session.commit()


def test_history_requires_a_token(client):
    assert client.get(f"{HISTORY_URL}/1").status_code == 401


def test_starting_a_quest_stores_the_npc_opening_as_the_first_message(client, headers, db_session):
    quest = start_starter(client, headers, db_session)

    response = client.get(f"{HISTORY_URL}/{quest.id}", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["quest_id"] == quest.id
    [opening] = body["messages"]
    assert opening["role"] == "npc"
    assert opening["text"] == quest.npc_opening
    assert opening["communication_success"] is None
    assert opening["created_at"]


def test_reading_the_history_twice_does_not_repeat_the_opening(client, headers, db_session):
    quest = start_starter(client, headers, db_session)

    client.get(f"{HISTORY_URL}/{quest.id}", headers=headers)
    second = client.get(f"{HISTORY_URL}/{quest.id}", headers=headers).json()

    assert len(second["messages"]) == 1
    assert db_session.scalar(select(func.count()).select_from(DialogueMessage)) == 1


def test_messages_come_back_in_the_order_they_were_written(client, headers, db_session):
    quest = start_starter(client, headers, db_session)
    add_messages(
        db_session,
        "deniz@example.com",
        quest,
        ("player", "Hi Alex! I am Deniz, I am from Izmir.", True),
        ("npc", "Nice to meet you, Deniz!", None),
        ("player", "I usually goes running on Sundays.", True),
    )

    messages = client.get(f"{HISTORY_URL}/{quest.id}", headers=headers).json()["messages"]

    assert [m["role"] for m in messages] == ["npc", "player", "npc", "player"]
    assert messages[1]["text"] == "Hi Alex! I am Deniz, I am from Izmir."
    assert messages[3]["communication_success"] is True
    assert [m["id"] for m in messages] == sorted(m["id"] for m in messages)


def test_a_completed_quest_keeps_its_history(client, headers, db_session):
    quest = start_starter(client, headers, db_session)
    progress = db_session.scalar(select(QuestProgress))
    progress.status = "completed"
    db_session.commit()

    response = client.get(f"{HISTORY_URL}/{quest.id}", headers=headers)

    assert response.status_code == 200
    assert len(response.json()["messages"]) == 1


def test_a_quest_never_started_has_no_history(client, headers, db_session):
    response = client.get(f"{HISTORY_URL}/{starter(db_session).id}", headers=headers)

    assert response.status_code == 404


def test_unknown_quest_is_404_and_a_non_number_is_422(client, headers):
    assert client.get(f"{HISTORY_URL}/9999", headers=headers).status_code == 404
    assert client.get(f"{HISTORY_URL}/abc", headers=headers).status_code == 422


def test_a_player_never_sees_another_players_conversation(client, headers, db_session):
    quest = start_starter(client, headers, db_session)
    add_messages(db_session, "deniz@example.com", quest, ("player", "My secret plan is...", True))
    other = login_headers(client, "ece@example.com")

    # Ece has not started the quest: Deniz's conversation looks like it does not exist
    assert client.get(f"{HISTORY_URL}/{quest.id}", headers=other).status_code == 404

    # Once Ece starts it, she sees only her own conversation
    assert client.post(f"/api/quests/{quest.id}/start", headers=other).status_code == 201
    messages = client.get(f"{HISTORY_URL}/{quest.id}", headers=other).json()["messages"]
    assert [m["text"] for m in messages] == [quest.npc_opening]
