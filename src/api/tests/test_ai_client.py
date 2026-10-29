"""GeminiClient: timeouts, the single retry, error mapping, and that secrets never leak."""

import json
import logging

import pytest

from app.core.config import Settings
from app.services.ai.client import DEFAULT_GEMINI_MODEL, AiError, GeminiClient, build_client
from tests.ai_fakes import FakeTransport, gemini_error, gemini_ok

KEY = "AIza-TEST-KEY-must-not-leak"
SYSTEM = "SYSTEM-PROMPT-SECRET"
USER = "PLAYER-TEXT-SECRET"


def make_client(transport: FakeTransport, sleeps: list[float] | None = None, **kwargs) -> GeminiClient:
    return GeminiClient(
        api_key=KEY,
        transport=transport,
        sleep=(sleeps.append if sleeps is not None else (lambda seconds: None)),
        **kwargs,
    )


def test_a_good_reply_is_returned_after_one_call():
    transport = FakeTransport(gemini_ok('{"ok": true}'))

    assert make_client(transport).complete(SYSTEM, USER) == '{"ok": true}'
    assert len(transport.calls) == 1


def test_request_asks_for_json_and_sends_the_key_in_a_header_not_the_url():
    transport = FakeTransport(gemini_ok("{}"))

    make_client(transport, model="some-model", timeout=7).complete(SYSTEM, USER)

    url, headers, body, timeout = transport.calls[0]
    sent = json.loads(body)
    assert url.endswith("/models/some-model:generateContent")
    assert KEY not in url
    assert headers["x-goog-api-key"] == KEY
    assert timeout == 7
    assert sent["generationConfig"]["responseMimeType"] == "application/json"
    assert sent["systemInstruction"]["parts"][0]["text"] == SYSTEM
    assert sent["contents"][0]["parts"][0]["text"] == USER


def test_reasoning_parts_are_skipped():
    payload = {"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True}, {"text": '{"a": 1}'}]}}]}

    transport = FakeTransport((200, json.dumps(payload).encode()))

    assert make_client(transport).complete(SYSTEM, USER) == '{"a": 1}'


@pytest.mark.parametrize(
    "first",
    [
        TimeoutError(),
        AiError("network", "URLError"),
        gemini_error(503, "UNAVAILABLE"),
        gemini_error(429, "RESOURCE_EXHAUSTED"),
    ],
    ids=["timeout", "network", "503", "429"],
)
def test_a_transient_failure_is_retried_exactly_once(first):
    transport = FakeTransport(first, gemini_ok("{}"))
    sleeps: list[float] = []

    assert make_client(transport, sleeps, retry_delay=0.5).complete(SYSTEM, USER) == "{}"
    assert len(transport.calls) == 2
    assert sleeps == [0.5]


def test_two_timeouts_in_a_row_give_up_after_two_calls():
    transport = FakeTransport(TimeoutError(), TimeoutError())

    with pytest.raises(AiError) as caught:
        make_client(transport).complete(SYSTEM, USER)

    assert caught.value.reason == "timeout"
    assert len(transport.calls) == 2


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (gemini_error(404, "NOT_FOUND"), "model_not_found"),
        (gemini_error(400, "INVALID_ARGUMENT", reason="API_KEY_INVALID"), "auth"),
        (gemini_error(403, "PERMISSION_DENIED"), "auth"),
        (gemini_error(401, "UNAUTHENTICATED"), "auth"),
        (gemini_error(400, "INVALID_ARGUMENT"), "bad_request"),
    ],
)
def test_permanent_failures_are_not_retried(response, reason):
    transport = FakeTransport(response)

    with pytest.raises(AiError) as caught:
        make_client(transport).complete(SYSTEM, USER)

    assert caught.value.reason == reason
    assert not caught.value.retryable
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "response",
    [
        (200, b"not json at all"),
        (200, json.dumps({"candidates": []}).encode()),
        (200, json.dumps({"candidates": [{"content": {"parts": []}}]}).encode()),
        (200, json.dumps({"candidates": [{"content": {"parts": [{"text": "   "}]}}]}).encode()),
    ],
    ids=["not-json", "no-candidates", "no-parts", "blank-text"],
)
def test_an_unusable_200_becomes_bad_response(response):
    with pytest.raises(AiError) as caught:
        make_client(FakeTransport(response)).complete(SYSTEM, USER)

    assert caught.value.reason == "bad_response"


def test_a_blocked_prompt_is_reported_as_blocked():
    payload = json.dumps({"promptFeedback": {"blockReason": "SAFETY"}}).encode()

    with pytest.raises(AiError) as caught:
        make_client(FakeTransport((200, payload))).complete(SYSTEM, USER)

    assert caught.value.reason == "blocked"


def test_error_messages_never_contain_the_key_the_prompt_or_provider_text():
    transport = FakeTransport(gemini_error(400, "INVALID_ARGUMENT"))

    with pytest.raises(AiError) as caught:
        make_client(transport).complete(SYSTEM, USER)

    text = str(caught.value)
    assert KEY not in text
    assert SYSTEM not in text and USER not in text
    assert "provider text that must never be copied" not in text


def test_logs_contain_only_metadata(caplog):
    transport = FakeTransport(gemini_error(503, "UNAVAILABLE"), gemini_ok("{}"))

    with caplog.at_level(logging.DEBUG, logger="speakquest.ai"):
        make_client(transport).complete(SYSTEM, USER)

    assert "attempt=1 outcome=unavailable" in caplog.text
    assert "attempt=2 outcome=ok" in caplog.text
    for secret in (KEY, SYSTEM, USER, "provider text that must never be copied"):
        assert secret not in caplog.text


def test_build_client_needs_provider_and_key():
    for settings in (
        Settings(_env_file=None, ai_provider="", ai_api_key="k"),
        Settings(_env_file=None, ai_provider="gemini", ai_api_key=""),
    ):
        with pytest.raises(AiError) as caught:
            build_client(settings)
        assert caught.value.reason == "not_configured"


def test_build_client_rejects_a_provider_that_is_not_implemented():
    with pytest.raises(AiError) as caught:
        build_client(Settings(_env_file=None, ai_provider="openai", ai_api_key="k"))

    assert caught.value.reason == "not_configured"
    assert "openai" in str(caught.value)


def test_build_client_uses_the_default_model_unless_one_is_configured():
    default = build_client(Settings(_env_file=None, ai_provider="Gemini", ai_api_key="k"))
    custom = build_client(Settings(_env_file=None, ai_provider="gemini", ai_api_key="k", ai_model="other-model"))

    assert isinstance(default, GeminiClient) and default._model == DEFAULT_GEMINI_MODEL
    assert custom._model == "other-model"
