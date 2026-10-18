from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import TOKEN_ALGORITHM, create_access_token

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"
ME_URL = "/api/auth/me"


@pytest.fixture
def registered_user(client):
    response = client.post(REGISTER_URL, json={"email": "alex@example.com", "password": "secret-pass"})
    assert response.status_code == 201
    return response.json()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_token_for_correct_credentials(client, registered_user):
    response = client.post(LOGIN_URL, json={"email": "alex@example.com", "password": "secret-pass"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert body["access_token"]


def test_login_accepts_email_in_any_case(client, registered_user):
    response = client.post(LOGIN_URL, json={"email": "  ALEX@Example.com ", "password": "secret-pass"})

    assert response.status_code == 200


def test_login_rejects_wrong_password(client, registered_user):
    response = client.post(LOGIN_URL, json={"email": "alex@example.com", "password": "wrong-pass"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


def test_login_gives_same_answer_for_unknown_email(client, registered_user):
    response = client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "secret-pass"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password."


def test_login_rejects_empty_password_without_echoing_email(client):
    response = client.post(LOGIN_URL, json={"email": "alex@example.com", "password": ""})

    assert response.status_code == 422
    assert "alex@example.com" not in response.text


def test_me_returns_logged_in_user(client, registered_user):
    token = client.post(
        LOGIN_URL, json={"email": "alex@example.com", "password": "secret-pass"}
    ).json()["access_token"]

    response = client.get(ME_URL, headers=auth_header(token))

    assert response.status_code == 200
    assert response.json() == registered_user


def test_me_requires_a_token(client):
    response = client.get(ME_URL)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        jwt.encode({"sub": "1"}, "some-other-secret", algorithm=TOKEN_ALGORITHM),
        jwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
            get_settings().secret_key,
            algorithm=TOKEN_ALGORITHM,
        ),
    ],
    ids=["garbage", "wrong-secret", "expired"],
)
def test_me_rejects_invalid_tokens(client, registered_user, token):
    response = client.get(ME_URL, headers=auth_header(token))

    assert response.status_code == 401


def test_me_rejects_token_of_deleted_user(client):
    response = client.get(ME_URL, headers=auth_header(create_access_token(999)))

    assert response.status_code == 401
