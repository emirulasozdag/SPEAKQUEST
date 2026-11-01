"""Structured logging and the request id.

Every log line of the "speakquest" loggers is one line of key=value pairs and carries the id of
the request it belongs to, so one request can be followed through the API, the dialogue flow and
the AI call. RequestContextMiddleware gives each API request an id, sends it back in the
X-Request-ID header, logs one line per request (endpoint, status, duration) and turns an
unexpected exception into the standard JSON error (core/errors.py) instead of a bare 500.

What is never logged: request or response bodies, query strings, headers, e-mail addresses,
passwords, tokens, API keys and the player's messages. The endpoint is logged as its route
template (/api/quests/{quest_id}), not the concrete path.
"""

import logging
import re
import time
import uuid
from contextvars import ContextVar

from starlette.types import ASGIApp, Message, Receive, Scope, Send

LOGGER_NAME = "speakquest"
REQUEST_ID_HEADER = "X-Request-ID"
# A caller may pass its own id (e.g. a proxy); anything else is replaced, so the header cannot be
# used to write arbitrary text into the logs
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

logger = logging.getLogger(f"{LOGGER_NAME}.request")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def build_handler(stream=None) -> logging.Handler:
    """A handler that writes key=value lines with the request id (stderr by default)."""
    handler = logging.StreamHandler(stream)
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        logging.Formatter(
            "ts=%(asctime)s level=%(levelname)s logger=%(name)s request_id=%(request_id)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    return handler


def configure_logging(level: int = logging.INFO) -> None:
    """Send the "speakquest" loggers to stderr as key=value lines. Safe to call more than once."""
    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(level)
    if any(getattr(handler, "_speakquest", False) for handler in root.handlers):
        return
    handler = build_handler()
    handler._speakquest = True  # type: ignore[attr-defined]
    root.addHandler(handler)


def new_request_id(incoming: str | None = None) -> str:
    if incoming and _VALID_REQUEST_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex[:16]


class RequestContextMiddleware:
    """Request id, one access log line per API request, and a JSON answer for unexpected errors."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope["path"].startswith("/api"):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        request_id = new_request_id(headers.get(REQUEST_ID_HEADER.lower().encode(), b"").decode("latin-1"))
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"] = [*message["headers"], (REQUEST_ID_HEADER.encode(), request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            logger.exception("unhandled error method=%s endpoint=%s", scope["method"], _endpoint(scope))
            if response_started:
                raise
            # Imported here: errors.py imports this module for the request id
            from app.core.errors import internal_error_response

            await internal_error_response(request_id)(scope, receive, send_with_id)
        finally:
            logger.info(
                "request method=%s endpoint=%s status=%d ms=%d",
                scope["method"],
                _endpoint(scope),
                status_code,
                (time.perf_counter() - started) * 1000,
            )
            request_id_var.reset(token)


def _endpoint(scope: Scope) -> str:
    """The route template when a route matched, so ids and other values stay out of the log."""
    route = scope.get("route")
    return getattr(route, "path_format", None) or getattr(route, "path", None) or "unmatched"
