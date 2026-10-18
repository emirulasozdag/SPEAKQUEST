from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import database_is_reachable
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness check used by the frontend status badge and by Docker."""
    return HealthResponse(
        status="ok",
        database="ok" if database_is_reachable() else "unavailable",
        environment=get_settings().environment,
    )
