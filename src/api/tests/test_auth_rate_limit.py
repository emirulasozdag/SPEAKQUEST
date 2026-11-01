import pytest

from app.core.config import get_settings
from app.core.rate_limit import TOO_MANY_ATTEMPTS, RateLimiter

REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"


@pytest.fixture
def low_limits(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "login_rate_limit", 3)
    monkeypatch.setattr(settings, "login_rate_window_seconds", 60)
    monkeypatch.setattr(settings, "register_rate_limit", 2)
    monkeypatch.setattr(settings, "register_rate_window_seconds", 60)
    return settings


@pytest.fixture
def registered_user(client):
    response = client.post(REGISTER_URL, json={"email": "alex@example.com", "password": "secret-pass"})
    assert response.status_code == 201


def login(client, email="alex@example.com", password="wrong-pass"):
    return client.post(LOGIN_URL, json={"email": email, "password": password})


def test_login_blocks_after_too_many_failed_attempts(client, low_limits, registered_user):
    for _ in range(3):
        assert login(client).status_code == 401

    response = login(client)

    assert response.status_code == 429
    assert response.json()["detail"] == TOO_MANY_ATTEMPTS
    assert 1 <= int(response.headers["Retry-After"]) <= 60


def test_blocked_login_rejects_even_the_correct_password(client, low_limits, registered_user):
    for _ in range(3):
        login(client)

    assert login(client, password="secret-pass").status_code == 429


def test_successful_login_resets_the_counter(client, low_limits, registered_user):
    login(client)
    login(client)
    assert login(client, password="secret-pass").status_code == 200

    # The two earlier failures no longer count
    for _ in range(3):
        assert login(client).status_code == 401
    assert login(client).status_code == 429


def test_login_limit_is_per_email(client, low_limits, registered_user):
    for _ in range(3):
        login(client)

    assert login(client, email="someone@example.com").status_code == 401


def test_blocked_answer_does_not_reveal_whether_account_exists(client, low_limits, registered_user):
    for _ in range(3):
        login(client)
        login(client, email="nobody@example.com")

    known = login(client)
    unknown = login(client, email="nobody@example.com")

    assert known.status_code == unknown.status_code == 429
    # Only the request id (different for every request) may differ
    known_body, unknown_body = known.json(), unknown.json()
    assert known_body.pop("request_id") != unknown_body.pop("request_id")
    assert known_body == unknown_body


def test_register_is_limited_per_ip(client, low_limits):
    for index in range(2):
        response = client.post(
            REGISTER_URL, json={"email": f"user{index}@example.com", "password": "secret-pass"}
        )
        assert response.status_code == 201

    response = client.post(REGISTER_URL, json={"email": "user9@example.com", "password": "secret-pass"})

    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_limiter_allows_again_after_window(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: now[0])
    limiter = RateLimiter()

    limiter.hit("key", window=60)
    limiter.hit("key", window=60)
    assert limiter.retry_after("key", limit=2, window=60) == 60

    now[0] += 30
    assert limiter.retry_after("key", limit=2, window=60) == 30

    now[0] += 30
    assert limiter.retry_after("key", limit=2, window=60) is None


def test_default_limits_come_from_settings():
    settings = get_settings()

    assert settings.login_rate_limit > 0
    assert settings.login_rate_window_seconds > 0
    assert settings.register_rate_limit > 0
    assert settings.register_rate_window_seconds > 0
