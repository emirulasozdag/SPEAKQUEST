"""One interface for the AI provider, and the Gemini implementation behind it.

The rest of the app only knows AiClient.complete(system, user) -> text. A provider failure
becomes an AiError with a short machine-readable reason; messages and logs never contain the API
key, the prompt or the player's text. Only transient failures are retried, and only once.
"""

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger("speakquest.ai")

DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Reasons that are worth one more try: the provider or the network hiccuped
RETRYABLE_REASONS = frozenset({"timeout", "network", "rate_limited", "unavailable"})


class AiError(Exception):
    """The AI provider could not give a usable answer. `reason` is stable and safe to log."""

    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(f"{reason}: {message}" if message else reason)
        self.reason = reason

    @property
    def retryable(self) -> bool:
        return self.reason in RETRYABLE_REASONS


class AiClient(Protocol):
    def complete(self, system: str, user: str) -> str:
        """Send one prompt and return the model's raw text. Raises AiError."""
        ...


# A transport sends one HTTP request and returns (status, body); tests replace it with a fake
Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def urllib_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise TimeoutError from None
        raise AiError("network", type(exc.reason).__name__) from None


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_GEMINI_MODEL,
        timeout: float = 20.0,
        transport: Transport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
        retry_delay: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._transport = transport
        self._sleep = sleep
        self._retry_delay = retry_delay

    def complete(self, system: str, user: str) -> str:
        try:
            return self._attempt(system, user, attempt=1)
        except AiError as first:
            if not first.retryable:
                raise
            self._sleep(self._retry_delay)
            return self._attempt(system, user, attempt=2)

    def _attempt(self, system: str, user: str, attempt: int) -> str:
        body = json.dumps(
            {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
            }
        ).encode()
        # The key goes in a header, not in the URL, so it can never end up in an error message
        headers = {"Content-Type": "application/json", "x-goog-api-key": self._api_key}
        started = time.perf_counter()
        try:
            try:
                status, payload = self._transport(GEMINI_URL.format(model=self._model), headers, body, self._timeout)
            except TimeoutError:
                raise AiError("timeout") from None
            if status != 200:
                raise _error_for_status(status, payload)
            text = _extract_text(payload)
        except AiError as exc:
            self._log(attempt, started, exc.reason)
            raise
        self._log(attempt, started, "ok")
        return text

    def _log(self, attempt: int, started: float, outcome: str) -> None:
        # Only metadata: never the prompt, the player's text or the key
        logger.info(
            "ai call provider=gemini model=%s attempt=%d outcome=%s ms=%d",
            self._model,
            attempt,
            outcome,
            (time.perf_counter() - started) * 1000,
        )


def _error_for_status(status: int, payload: bytes) -> AiError:
    provider_status = _provider_error_status(payload)
    if status == 429:
        return AiError("rate_limited", provider_status)
    if status >= 500:
        return AiError("unavailable", provider_status)
    if status == 404:
        # Models are retired quickly (gemini-2.5-flash was closed to new users): say so clearly
        return AiError("model_not_found", "check AI_MODEL")
    if status in (401, 403) or "API_KEY" in provider_status:
        return AiError("auth", "check AI_API_KEY")
    return AiError("bad_request", f"HTTP {status} {provider_status}".strip())


def _provider_error_status(payload: bytes) -> str:
    """The provider's short status word (e.g. UNAVAILABLE), never its free-text message."""
    try:
        error = json.loads(payload).get("error", {})
        details = error.get("details") or []
        reasons = [d.get("reason", "") for d in details if isinstance(d, dict)]
        return str(reasons[0] if reasons and reasons[0] else error.get("status", ""))[:40]
    except (ValueError, AttributeError):
        return ""


def _extract_text(payload: bytes) -> str:
    try:
        data = json.loads(payload)
        if data.get("promptFeedback", {}).get("blockReason"):
            raise AiError("blocked")
        parts = data["candidates"][0]["content"]["parts"]
        # Reasoning models may send "thought" parts first; only the answer parts are text we want
        text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    except AiError:
        raise
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise AiError("bad_response") from None
    if not text.strip():
        raise AiError("bad_response", "empty text")
    return text


def build_client(settings: Settings) -> AiClient:
    """The client for the configured provider. Raises AiError('not_configured') if there is none."""
    provider = settings.ai_provider.strip().lower()
    if not provider or not settings.ai_api_key:
        raise AiError("not_configured", "set AI_PROVIDER and AI_API_KEY")
    if provider == "gemini":
        return GeminiClient(
            api_key=settings.ai_api_key,
            model=settings.ai_model or DEFAULT_GEMINI_MODEL,
            timeout=settings.ai_timeout_seconds,
        )
    raise AiError("not_configured", f"provider {provider!r} is not supported yet")
