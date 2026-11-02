"""Account management: changing the password and resetting the game progress."""

import pytest
from sqlalchemy import func, select

from app.content.seed import seed_content
from app.models import Base
from app.models.dialogue import DialogueMessage
from app.models.player import PlayerProfile
from app.models.quest_progress import QuestProgress
from app.models.user import User
from app.services.players import PROGRESS_MODELS
from tests.test_player_profile import VALID_PROFILE, login_headers
from tests.test_quest_complete import meet_objectives
from tests.test_story_state import EMAIL, quest_by_slug

CHANGE_URL = "/api/auth/change-password"
RESET_URL = "/api/player/reset"
PASSWORD = "secret-pass"
OTHER_EMAIL = "other@example.com"


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


def new_player(client, email: str = EMAIL) -> dict[str, str]:
    headers = login_headers(client, email)
    assert client.put("/api/player/profile", json=VALID_PROFILE, headers=headers).status_code == 201
    return headers


def user_id(db_session, email: str) -> int:
    return db_session.scalar(select(User.id).where(User.email == email))


def progress_rows(db_session, uid: int) -> int:
    """Rows of every progress table for this player, dialogue messages included."""
    rows = sum(
        db_session.scalar(select(func.count()).select_from(model).where(model.user_id == uid))
        for model in PROGRESS_MODELS
    )
    messages = db_session.scalar(
        select(func.count())
        .select_from(DialogueMessage)
        .join(QuestProgress, QuestProgress.id == DialogueMessage.quest_progress_id)
        .where(QuestProgress.user_id == uid)
    )
    return rows + messages


def play_a_little(client, headers, db_session) -> None:
    """Play the first quest with its decision, then start the next one."""
    starter = quest_by_slug(db_session, "meet_your_neighbor")
    assert client.post(f"/api/quests/{starter.id}/start", headers=headers).status_code == 201
    payload = {"quest_id": starter.id, "decision_id": "help_alex_move", "option_id": "help"}
    assert client.post("/api/story/decision", json=payload, headers=headers).status_code == 201
    meet_objectives(db_session, EMAIL, starter)
    assert client.post(f"/api/quests/{starter.id}/complete", headers=headers).status_code == 200
    cafe = quest_by_slug(db_session, "morning_at_the_cafe")
    assert client.post(f"/api/quests/{cafe.id}/start", headers=headers).status_code == 201


def login_status(client, email: str, password: str) -> int:
    return client.post("/api/auth/login", json={"email": email, "password": password}).status_code


# --- change password -------------------------------------------------------------------------


def test_change_password_requires_a_token(client):
    response = client.post(CHANGE_URL, json={"current_password": PASSWORD, "new_password": "new-secret"})

    assert response.status_code == 401


def test_changing_the_password_replaces_the_old_one(client, db_session):
    headers = login_headers(client, EMAIL)
    old_hash = db_session.scalar(select(User.password_hash).where(User.email == EMAIL))

    response = client.post(CHANGE_URL, json={"current_password": PASSWORD, "new_password": "new-secret"}, headers=headers)

    assert response.status_code == 204
    new_hash = db_session.scalar(select(User.password_hash).where(User.email == EMAIL))
    assert new_hash != old_hash and new_hash.startswith("$2")
    assert "new-secret" not in new_hash
    assert login_status(client, EMAIL, "new-secret") == 200
    assert login_status(client, EMAIL, PASSWORD) == 401


def test_a_wrong_current_password_changes_nothing(client):
    headers = login_headers(client, EMAIL)

    response = client.post(CHANGE_URL, json={"current_password": "wrong-pass", "new_password": "new-secret"}, headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Your current password is incorrect."
    assert login_status(client, EMAIL, PASSWORD) == 200


@pytest.mark.parametrize("new_password", ["short", "x" * 73, "é" * 40], ids=["too-short", "too-long", "over-72-bytes"])
def test_the_new_password_follows_the_sign_up_rules(client, new_password):
    headers = login_headers(client, EMAIL)

    response = client.post(CHANGE_URL, json={"current_password": PASSWORD, "new_password": new_password}, headers=headers)

    assert response.status_code == 422
    assert login_status(client, EMAIL, PASSWORD) == 200


def test_changing_one_password_leaves_other_accounts_alone(client):
    headers = login_headers(client, EMAIL)
    login_headers(client, OTHER_EMAIL)

    client.post(CHANGE_URL, json={"current_password": PASSWORD, "new_password": "new-secret"}, headers=headers)

    assert login_status(client, OTHER_EMAIL, PASSWORD) == 200


# --- reset game progress ---------------------------------------------------------------------


def test_reset_requires_a_token(client):
    assert client.post(RESET_URL).status_code == 401


def test_reset_without_a_character_is_not_found(client):
    headers = login_headers(client, EMAIL)

    assert client.post(RESET_URL, headers=headers).status_code == 404


def test_reset_deletes_all_progress_and_starts_the_story_again(client, db_session):
    headers = new_player(client)
    play_a_little(client, headers, db_session)
    uid = user_id(db_session, EMAIL)
    assert client.get("/api/player/profile", headers=headers).json()["xp"] > 0

    response = client.post(RESET_URL, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert (body["xp"], body["level"]) == (0, 1)
    assert body["character_name"] == VALID_PROFILE["character_name"]
    # Only the fresh story state of a new character is left
    assert progress_rows(db_session, uid) == 1
    story = client.get("/api/story/state", headers=headers).json()
    assert (story["chapter"], story["flags"], story["current_location"]) == (1, [], None)
    assert all(npc["trust"] == 0 for npc in story["npcs"])
    statuses = {quest["slug"]: quest["status"] for quest in client.get("/api/quests", headers=headers).json()}
    assert statuses["meet_your_neighbor"] == "available"
    assert "active" not in statuses.values() and "completed" not in statuses.values()


def test_after_a_reset_the_game_can_be_played_again(client, db_session):
    headers = new_player(client)
    play_a_little(client, headers, db_session)
    client.post(RESET_URL, headers=headers)

    starter = quest_by_slug(db_session, "meet_your_neighbor")
    assert client.post(f"/api/quests/{starter.id}/start", headers=headers).status_code == 201
    payload = {"quest_id": starter.id, "decision_id": "help_alex_move", "option_id": "not_now"}

    assert client.post("/api/story/decision", json=payload, headers=headers).status_code == 201


def test_reset_keeps_the_account_and_the_character(client, db_session):
    headers = new_player(client)
    play_a_little(client, headers, db_session)

    client.post(RESET_URL, headers=headers)

    assert db_session.scalar(select(func.count()).select_from(User)) == 1
    assert db_session.scalar(select(func.count()).select_from(PlayerProfile)) == 1
    assert client.get("/api/auth/me", headers=headers).status_code == 200


def test_one_players_reset_does_not_touch_another_player(client, db_session):
    headers_a = new_player(client)
    play_a_little(client, headers_a, db_session)
    headers_b = new_player(client, OTHER_EMAIL)
    starter = quest_by_slug(db_session, "meet_your_neighbor")
    assert client.post(f"/api/quests/{starter.id}/start", headers=headers_b).status_code == 201
    uid_b = user_id(db_session, OTHER_EMAIL)
    rows_b = progress_rows(db_session, uid_b)
    profile_b = client.get("/api/player/profile", headers=headers_b).json()

    assert client.post(RESET_URL, headers=headers_a).status_code == 200

    assert progress_rows(db_session, uid_b) == rows_b
    assert client.get("/api/player/profile", headers=headers_b).json()["xp"] == profile_b["xp"]


def test_every_table_with_player_progress_is_reset():
    """A new table that points at users (other than the character itself) must be in PROGRESS_MODELS,
    and a table that points at quest progress must be handled by delete_progress()."""
    def referencing(table_name: str) -> set[str]:
        return {
            table.name
            for table in Base.metadata.sorted_tables
            if any(fk.column.table.name == table_name for fk in table.foreign_keys)
        }

    assert referencing("users") - {"player_profiles"} == {model.__tablename__ for model in PROGRESS_MODELS}
    assert referencing("quest_progress") == {"dialogue_messages"}
