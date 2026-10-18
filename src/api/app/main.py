"""FastAPI entry point: registers the API routers and serves the static frontend."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.core.errors import validation_error_handler
from app.routers import auth, dialogue, health, learning, locations, player, quests, story

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_exception_handler(RequestValidationError, validation_error_handler)

for router in (health, auth, player, locations, quests, dialogue, learning, story):
    app.include_router(router.router, prefix="/api")

# Mounted last so /api/* routes take precedence over static files
if settings.frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
