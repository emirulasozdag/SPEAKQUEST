import pytest

from app.core.config import get_settings
from app.core.rate_limit import TOO_MANY_ATTEMPTS, RateLimiter
from app.routers.auth import login_limiter

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


# --- password checks on a logged-in account (#71) -----------------------------------------------

CHANGE_URL = "/api/auth/change-password"


@pytest.fixture
def few_password_checks(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "password_check_rate_limit", 3)
    monkeypatch.setattr(settings, "password_check_rate_window_seconds", 900)


@pytest.fixture
def session(client, registered_user) -> dict[str, str]:
    token = client.post(LOGIN_URL, json={"email": "alex@example.com", "password": "secret-pass"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def change(client, headers, current="wrong-pass"):
    return client.post(CHANGE_URL, json={"current_password": current, "new_password": "new-secret"}, headers=headers)


def delete(client, headers, password="wrong-pass"):
    return client.request("DELETE", "/api/auth/me", json={"password": password}, headers=headers)


def test_wrong_passwords_on_change_password_are_limited(client, few_password_checks, session):
    for _ in range(3):
        assert change(client, session).status_code == 403

    response = change(client, session)

    assert response.status_code == 429
    assert response.json()["detail"] == TOO_MANY_ATTEMPTS
    assert 1 <= int(response.headers["Retry-After"]) <= 900
    # Even the right password waits now: guessing has to stop
    assert change(client, session, current="secret-pass").status_code == 429


def test_delete_account_shares_the_same_password_limit(client, few_password_checks, session):
    change(client, session)
    change(client, session)
    assert delete(client, session).status_code == 403

    assert delete(client, session, password="secret-pass").status_code == 429
    assert client.get("/api/auth/me", headers=session).status_code == 200


def test_a_successful_change_clears_the_count(client, few_password_checks, session):
    change(client, session)
    change(client, session)
    new_token = change(client, session, current="secret-pass").json()["access_token"]
    headers = {"Authorization": f"Bearer {new_token}"}

    for _ in range(3):
        assert change(client, headers).status_code == 403
    assert change(client, headers).status_code == 429


def test_the_password_limit_is_per_account(client, few_password_checks, session):
    for _ in range(3):
        change(client, session)
    client.post(REGISTER_URL, json={"email": "other@example.com", "password": "secret-pass"})
    token = client.post(LOGIN_URL, json={"email": "other@example.com", "password": "secret-pass"}).json()["access_token"]

    assert change(client, {"Authorization": f"Bearer {token}"}).status_code == 403


# --- memory: only active keys are kept (#76) ----------------------------------------------------


@pytest.fixture
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr("app.core.rate_limit.time.monotonic", lambda: now[0])
    return now


def test_asking_about_a_key_never_stores_it(clock):
    limiter = RateLimiter()

    for index in range(100):
        assert limiter.retry_after(f"user{index}@example.com|1.2.3.4", limit=5, window=60) is None

    assert len(limiter) == 0


def test_a_key_whose_hits_left_the_window_is_removed_when_asked_again(clock):
    limiter = RateLimiter()
    limiter.hit("key", window=60)
    clock[0] += 61

    assert limiter.retry_after("key", limit=1, window=60) is None
    assert len(limiter) == 0


def test_a_periodic_sweep_drops_expired_keys_and_keeps_active_ones(clock):
    limiter = RateLimiter()
    for index in range(1000):
        limiter.hit(f"old{index}", window=60)
    clock[0] += 30
    limiter.hit("recent", window=60)
    assert len(limiter) == 1001

    # Past the old keys' window and past the sweep interval: the next hit sweeps
    clock[0] += 40
    limiter.hit("new", window=60)

    assert len(limiter) == 2
    assert limiter.retry_after("recent", limit=1, window=60) is not None


def test_keys_with_a_long_window_survive_a_sweep(clock):
    limiter = RateLimiter()
    limiter.hit("password-check", window=900)
    clock[0] += RateLimiter.SWEEP_INTERVAL + 1
    limiter.hit("other", window=60)

    assert limiter.retry_after("password-check", limit=1, window=900) is not None


def test_many_failed_logins_with_different_emails_do_not_pile_up(client, clock):
    for index in range(50):
        client.post(LOGIN_URL, json={"email": f"nobody{index}@example.com", "password": "wrong-pass"})
    stored = len(login_limiter)
    assert stored == 50

    clock[0] += 120
    client.post(LOGIN_URL, json={"email": "last@example.com", "password": "wrong-pass"})

    assert len(login_limiter) == 1
