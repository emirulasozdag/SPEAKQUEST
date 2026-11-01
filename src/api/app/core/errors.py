"""Shared exception handlers and the one JSON error format of the API.

Every error answer has the same shape:

    {"detail": "One sentence for the player", "request_id": "..."}

For validation errors (422) "detail" is a list of {"loc", "msg", "type"} instead, without the
submitted values. "request_id" is also sent in the X-Request-ID header and appears in every log
line of that request, so a reported error can be found in the logs. An unexpected exception never
shows its message or traceback to the caller: they go to the log only.
"""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import request_id_var

INTERNAL_ERROR = "Something went wrong on our side. Please try again in a moment."


def error_body(detail, request_id: str | None = None) -> dict:
    return {"detail": detail, "request_id": request_id or request_id_var.get()}


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return validation errors without echoing submitted values (they may contain passwords)."""
    errors = [
        {"loc": error["loc"], "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_body(errors))


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """HTTPException as raised by the routers (and 404/405 from routing), in the standard shape."""
    return JSONResponse(status_code=exc.status_code, content=error_body(exc.detail), headers=exc.headers)


def internal_error_response(request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(INTERNAL_ERROR, request_id),
    )
