from sqlalchemy import func, select

from app.models import Base
from app.models.user import User
from app.services.users import PLAYER_DATA_MODELS

ME_URL = "/api/auth/me"
PROFILE_URL = "/api/player/profile"
PASSWORD = "secret-pass"

PROFILE = {
    "character_name": "Deniz",
    "avatar": 2,
    "english_level": "B1",
    "learning_goal": "work",
}


def create_player(client, email: str) -> dict[str, str]:
    """Register, log in and create a character; returns the auth header."""
    assert client.post("/api/auth/register", json={"email": email, "password": PASSWORD}).status_code == 201
    token = client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.put(PROFILE_URL, json=PROFILE, headers=headers).status_code == 201
    return headers


def delete_me(client, headers, password=PASSWORD):
    return client.request("DELETE", ME_URL, json={"password": password}, headers=headers)


def player_row_count(db_session, user_id: int) -> int:
    return sum(
        db_session.scalar(select(func.count()).select_from(model).where(model.user_id == user_id))
        for model in PLAYER_DATA_MODELS
    )


def test_delete_account_removes_user_and_all_player_data(client, db_session):
    headers = create_player(client, "deniz@example.com")
    user_id = client.get(ME_URL, headers=headers).json()["id"]
    assert player_row_count(db_session, user_id) > 0

    response = delete_me(client, headers)

    assert response.status_code == 204
    assert db_session.get(User, user_id) is None
    assert player_row_count(db_session, user_id) == 0


def test_wrong_password_deletes_nothing(client, db_session):
    headers = create_player(client, "deniz@example.com")
    user_id = client.get(ME_URL, headers=headers).json()["id"]

    response = delete_me(client, headers, password="wrong-pass")

    assert response.status_code == 403
    assert response.json()["detail"] == "Incorrect password."
    assert db_session.get(User, user_id) is not None
    assert client.get(PROFILE_URL, headers=headers).status_code == 200


def test_password_is_required(client):
    headers = create_player(client, "deniz@example.com")

    assert client.request("DELETE", ME_URL, json={}, headers=headers).status_code == 422


def test_delete_requires_a_token(client):
    assert client.request("DELETE", ME_URL, json={"password": PASSWORD}).status_code == 401


def test_token_of_deleted_account_stops_working(client):
    headers = create_player(client, "deniz@example.com")
    assert delete_me(client, headers).status_code == 204

    assert client.get(ME_URL, headers=headers).status_code == 401
    assert client.get(PROFILE_URL, headers=headers).status_code == 401
    assert delete_me(client, headers).status_code == 401


def test_deleting_one_account_keeps_other_players_data(client, db_session):
    headers_a = create_player(client, "a@example.com")
    headers_b = create_player(client, "b@example.com")
    user_b = client.get(ME_URL, headers=headers_b).json()["id"]
    rows_before = player_row_count(db_session, user_b)

    assert delete_me(client, headers_a).status_code == 204

    assert client.get(PROFILE_URL, headers=headers_b).json()["character_name"] == PROFILE["character_name"]
    assert player_row_count(db_session, user_b) == rows_before


def test_email_can_register_again_after_deletion(client):
    headers = create_player(client, "deniz@example.com")
    assert delete_me(client, headers).status_code == 204

    response = client.post("/api/auth/register", json={"email": "deniz@example.com", "password": PASSWORD})

    assert response.status_code == 201


def test_every_table_with_player_data_is_deleted():
    """A new table that points at users must be added to PLAYER_DATA_MODELS."""
    tables_with_user_id = {
        table.name
        for table in Base.metadata.sorted_tables
        if any(fk.column.table.name == "users" for fk in table.foreign_keys)
    }
    listed = {model.__tablename__ for model in PLAYER_DATA_MODELS}

    assert tables_with_user_id == listed
