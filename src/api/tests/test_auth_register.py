from sqlalchemy import select

from app.core.security import verify_password
from app.models import User

REGISTER_URL = "/api/auth/register"


def test_register_creates_user_with_hashed_password(client, db_session):
    response = client.post(REGISTER_URL, json={"email": "alex@example.com", "password": "secret-pass"})

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "alex@example.com"
    assert set(body) == {"id", "email", "created_at"}

    user = db_session.scalar(select(User).where(User.email == "alex@example.com"))
    assert user is not None
    assert user.password_hash != "secret-pass"
    assert verify_password("secret-pass", user.password_hash)


def test_register_normalizes_email(client):
    response = client.post(REGISTER_URL, json={"email": "  Alex@Example.COM ", "password": "secret-pass"})

    assert response.status_code == 201
    assert response.json()["email"] == "alex@example.com"


def test_register_rejects_duplicate_email(client):
    client.post(REGISTER_URL, json={"email": "alex@example.com", "password": "secret-pass"})

    response = client.post(REGISTER_URL, json={"email": "ALEX@example.com", "password": "other-pass"})

    assert response.status_code == 409


def test_register_rejects_invalid_email(client):
    response = client.post(REGISTER_URL, json={"email": "not-an-email", "password": "secret-pass"})

    assert response.status_code == 422


def test_register_rejects_short_password_without_echoing_it(client):
    response = client.post(REGISTER_URL, json={"email": "alex@example.com", "password": "short"})

    assert response.status_code == 422
    assert "short" not in response.text.replace("string_too_short", "")


def test_register_rejects_password_over_bcrypt_limit(client):
    response = client.post(REGISTER_URL, json={"email": "alex@example.com", "password": "é" * 40})

    assert response.status_code == 422
