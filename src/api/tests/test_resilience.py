"""Request ids, structured logs, the standard JSON error format and the dialogue rate limit (#19)."""

import io
import logging

import pytest

from app.content.seed import seed_content
from app.core.config import get_settings
from app.core.errors import INTERNAL_ERROR
from app.core.logging import LOGGER_NAME, REQUEST_ID_HEADER, build_handler
from app.main import app
from app.routers.dialogue import TOO_MANY_MESSAGES
from app.services.ai.client import get_ai_client
from tests.ai_fakes import reply_json
from tests.test_dialogue_message import headers, interview, send, use_ai  # noqa: F401
from tests.test_player_profile import login_headers


@pytest.fixture(autouse=True)
def seeded(db_session):
    seed_content(db_session)


@pytest.fixture
def log_lines():
    """The lines the app's own handler writes, exactly as they would reach the console."""
    stream = io.StringIO()
    handler = build_handler(stream)
    logger = logging.getLogger(LOGGER_NAME)
    logger.addHandler(handler)
    yield lambda: stream.getvalue().splitlines()
    logger.removeHandler(handler)


# --- request id ------------------------------------------------------------------------------


def test_every_api_response_carries_a_new_request_id(client):
    first = client.get("/api/health").headers[REQUEST_ID_HEADER]
    second = client.get("/api/health").headers[REQUEST_ID_HEADER]

    assert first and second and first != second


def test_a_valid_incoming_request_id_is_kept(client):
    response = client.get("/api/health", headers={REQUEST_ID_HEADER: "proxy-abc_123"})

    assert response.headers[REQUEST_ID_HEADER] == "proxy-abc_123"


@pytest.mark.parametrize("bad", ["has space", "a" * 65, "new\tline", "x;drop", ""])
def test_an_unsafe_incoming_request_id_is_replaced(client, bad):
    response = client.get("/api/health", headers={REQUEST_ID_HEADER: bad})

    assert response.headers[REQUEST_ID_HEADER] != bad
    assert len(response.headers[REQUEST_ID_HEADER]) == 16


# --- the standard error format ---------------------------------------------------------------


def test_an_http_error_has_detail_and_the_request_id(client, headers):  # noqa: F811
    response = client.get("/api/dialogue/history/9999", headers=headers)

    assert response.status_code == 404
    assert response.json() == {
        "detail": "You have not started this quest.",
        "request_id": response.headers[REQUEST_ID_HEADER],
    }


def test_an_unknown_api_route_answers_in_the_same_format(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert set(response.json()) == {"detail", "request_id"}


def test_a_validation_error_lists_the_fields_without_the_submitted_values(client):
    response = client.post("/api/auth/register", json={"email": "not-an-email", "password": "hunter2-secret"})

    assert response.status_code == 422
    body = response.json()
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]
    assert isinstance(body["detail"], list) and body["detail"]
    assert "hunter2-secret" not in response.text and "not-an-email" not in response.text


def test_an_unexpected_error_is_a_json_500_without_internals_and_is_logged(
    client, headers, interview, log_lines  # noqa: F811
):
    def broken_client():
        raise RuntimeError("database password is hunter2")

    app.dependency_overrides[get_ai_client] = broken_client

    response = send(client, headers, "Hello there.")

    assert response.status_code == 500
    request_id = response.headers[REQUEST_ID_HEADER]
    assert response.json() == {"detail": INTERNAL_ERROR, "request_id": request_id}
    assert "hunter2" not in response.text and "Traceback" not in response.text
    logged = "\n".join(log_lines())
    assert f"request_id={request_id} unhandled error method=POST endpoint=/api/dialogue/message" in logged
    assert "RuntimeError" in logged  # the traceback is in the log, for the developer


# --- structured logs -------------------------------------------------------------------------


def test_each_api_request_is_logged_once_with_endpoint_status_and_duration(client, headers, log_lines):  # noqa: F811
    response = client.get("/api/dialogue/history/123", headers=headers)

    request_id = response.headers[REQUEST_ID_HEADER]
    [line] = [
        line for line in log_lines() if f"request_id={request_id}" in line and "logger=speakquest.request" in line
    ]
    # The route template, not the concrete id
    assert "method=GET endpoint=/api/dialogue/history/{quest_id} status=404 ms=" in line
    assert line.startswith("ts=") and "level=INFO" in line


def test_logs_never_contain_emails_passwords_tokens_or_query_strings(client, log_lines):
    client.post("/api/auth/register", json={"email": "secret.person@example.com", "password": "my-password-1"})
    token = client.post(
        "/api/auth/login", json={"email": "secret.person@example.com", "password": "my-password-1"}
    ).json()["access_token"]
    client.get("/api/learning/errors?category=past_simple", headers={"Authorization": f"Bearer {token}"})

    logged = "\n".join(log_lines())
    assert "endpoint=/api/learning/errors status=200" in logged
    for secret in ("secret.person", "my-password-1", token, "category=past_simple"):
        assert secret not in logged


def test_the_ai_step_of_a_message_is_logged_with_its_duration_and_request_id(
    client, headers, interview, log_lines  # noqa: F811
):
    use_ai(reply_json())

    response = send(client, headers, "I worked in a restaurant.")

    request_id = response.headers[REQUEST_ID_HEADER]
    [line] = [line for line in log_lines() if "ai analysis" in line]
    assert f"request_id={request_id}" in line
    assert "outcome=ok ms=" in line
    assert "restaurant" not in "\n".join(log_lines())  # the player's text never reaches the log


def test_static_pages_are_not_logged_as_api_requests(client, log_lines):
    client.get("/")

    assert not [line for line in log_lines() if "logger=speakquest.request" in line]


# --- dialogue rate limit ---------------------------------------------------------------------


@pytest.fixture
def low_limit(monkeypatch):
    monkeypatch.setattr(get_settings(), "dialogue_rate_limit", 2)


def test_the_default_limit_is_a_few_messages_per_minute():
    settings = get_settings()

    assert 1 < settings.dialogue_rate_limit <= 20
    assert settings.dialogue_rate_window_seconds == 60


def test_a_player_who_sends_too_fast_gets_429_and_the_ai_is_not_called(
    client, headers, interview, low_limit  # noqa: F811
):
    fake = use_ai(reply_json(), reply_json())
    assert send(client, headers, "One.").status_code == 200
    assert send(client, headers, "Two.").status_code == 200

    blocked = send(client, headers, "Three.")

    assert blocked.status_code == 429
    assert blocked.json()["detail"] == TOO_MANY_MESSAGES
    assert 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert len(fake.calls) == 2


def test_attempts_the_ai_could_not_answer_count_too(client, headers, interview, low_limit):  # noqa: F811
    use_ai("not json", "still not json", "nope", "nope again")
    assert send(client, headers, "One.").json()["status"] == "ai_unavailable"
    assert send(client, headers, "Two.").json()["status"] == "ai_unavailable"

    assert send(client, headers, "Three.").status_code == 429


def test_the_limit_is_per_player(client, headers, interview, low_limit):  # noqa: F811
    use_ai(reply_json(), reply_json())
    send(client, headers, "One.")
    send(client, headers, "Two.")
    assert send(client, headers, "Three.").status_code == 429

    other = login_headers(client, "other@example.com")
    # Another player is not blocked: without a character they get the normal 409, not 429
    assert send(client, other, "Hello.").status_code == 409
