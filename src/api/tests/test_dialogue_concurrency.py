"""#72: dialogue messages that overlap in time.

The AI call runs outside any transaction, so these tests run "the other request" while the AI is
answering: a hook replaces analyze_message, does its work, then lets the real analysis finish.
"""

import threading
import time

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.dialogue import DialogueMessage
from app.models.quest_progress import QuestProgress
from app.models.user import User
from app.services import dialogue as dialogue_service
from app.services.players import reset_progress
from app.services.users import delete_account
from tests.ai_fakes import reply_json
from tests.conftest import TEST_DATABASE_URL
from tests.test_dialogue_message import EMAIL, MESSAGE_URL, headers, interview, seeded, send, use_ai  # noqa: F401


def user_id(db_session) -> int:
    return db_session.scalar(select(User.id).where(User.email == EMAIL))


def progress(db_session, quest) -> QuestProgress | None:
    return db_session.execute(
        select(QuestProgress)
        .where(QuestProgress.quest_template_id == quest.id)
        .execution_options(populate_existing=True)
    ).scalar_one_or_none()


def messages(db_session) -> int:
    return db_session.scalar(select(func.count()).select_from(DialogueMessage))


@pytest.fixture
def while_ai_answers(monkeypatch):
    """Run `action` once, during the first AI call, then let that call finish normally."""
    real = dialogue_service.analyze_message
    pending = []

    def hooked(client, context, text):
        if pending:
            pending.pop()()
        return real(client, context, text)

    monkeypatch.setattr(dialogue_service, "analyze_message", hooked)
    return pending.append


def test_no_transaction_is_open_while_the_ai_answers(client, headers, interview, db_session, while_ai_answers):  # noqa: F811
    seen = []
    while_ai_answers(lambda: seen.append(db_session.in_transaction()))
    use_ai(reply_json())

    assert send(client, headers, "Last year I work in a restaurant.").status_code == 200
    assert seen == [False]


def test_two_messages_at_once_keep_both_objectives(client, headers, interview, db_session, while_ai_answers):  # noqa: F811
    fake = use_ai(
        # The second message is answered first, while the first one waits for its reply
        reply_json(objectives_met=["describe_experience"]),
        reply_json(objectives_met=["introduce_yourself"]),
    )
    uid = user_id(db_session)

    def other_request():
        # Another request has its own session, as in the running app
        with Session(db_session.get_bind(), expire_on_commit=False) as other:
            dialogue_service.send_message(other, uid, "I worked as a waiter.", fake)

    while_ai_answers(other_request)

    assert send(client, headers, "Hello, I am Deniz.").status_code == 200

    met = progress(db_session, interview).objectives_met
    assert set(met) == {"introduce_yourself", "describe_experience"}


def test_a_quest_completed_meanwhile_gets_no_message_and_a_clear_409(client, headers, interview, db_session, while_ai_answers):  # noqa: F811
    use_ai(reply_json(suggested_story_action="interview_positive"))
    before = messages(db_session)

    def complete_it():
        db_session.execute(update(QuestProgress).values(status="completed"))
        db_session.commit()

    while_ai_answers(complete_it)
    response = send(client, headers, "Thank you for your time.")

    assert response.status_code == 409
    assert "Nothing was saved" in response.json()["detail"]
    assert messages(db_session) == before
    trust = client.get("/api/story/state", headers=headers).json()["npcs"]
    assert all(npc["trust"] == 0 for npc in trust if npc["slug"] == "olivia")


def test_a_reset_meanwhile_is_a_409_not_a_server_error(client, headers, interview, db_session, while_ai_answers):  # noqa: F811
    use_ai(reply_json())
    while_ai_answers(lambda: reset_progress(db_session, user_id(db_session)))

    response = send(client, headers, "Last year I work in a restaurant.")

    assert response.status_code == 409
    assert progress(db_session, interview) is None
    assert messages(db_session) == 0


def test_an_account_deleted_meanwhile_is_a_409_not_a_server_error(client, headers, interview, db_session, while_ai_answers):  # noqa: F811
    use_ai(reply_json())

    def delete_it():
        user = db_session.get(User, user_id(db_session))
        assert delete_account(db_session, user, "secret-pass")

    while_ai_answers(delete_it)
    response = send(client, headers, "Last year I work in a restaurant.")

    assert response.status_code == 409
    assert messages(db_session) == 0


def test_a_normal_message_still_saves_everything(client, headers, interview, db_session):  # noqa: F811
    use_ai(reply_json(objectives_met=["introduce_yourself"]))

    assert send(client, headers, "Hello, I am Deniz.").status_code == 200

    assert progress(db_session, interview).objectives_met == ["introduce_yourself"]
    # The player's message and the NPC's reply, after the NPC's opening line
    assert messages(db_session) == 3


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="needs PostgreSQL: SQLite in tests has one shared connection")
def test_two_real_requests_at_the_same_time_on_postgresql(client, headers, interview, db_session):  # noqa: F811
    """Two threads, each with its own session and a slow AI, write to the same quest at once."""
    uid = user_id(db_session)
    db_session.commit()
    barrier = threading.Barrier(2)

    class SlowAi:
        def __init__(self, objective: str) -> None:
            self.reply = reply_json(objectives_met=[objective])

        def complete(self, system: str, user: str) -> str:
            barrier.wait(timeout=5)  # both requests are inside the AI call together
            time.sleep(0.2)
            return self.reply

    errors = []

    def player_sends(objective: str) -> None:
        try:
            with Session(db_session.get_bind(), expire_on_commit=False) as own:
                dialogue_service.send_message(own, uid, f"Message about {objective}.", SlowAi(objective))
        except Exception as error:  # noqa: BLE001 - reported below
            errors.append(error)

    threads = [threading.Thread(target=player_sends, args=(o,)) for o in ("introduce_yourself", "describe_experience")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert set(progress(db_session, interview).objectives_met) == {"introduce_yourself", "describe_experience"}
