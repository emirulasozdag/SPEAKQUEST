"""Application settings, loaded from environment variables (and an optional .env file)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/frontend when running locally, /frontend inside the Docker container
DEFAULT_FRONTEND_DIR = Path(__file__).resolve().parents[3] / "frontend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "SpeakQuest API"
    environment: str = "development"

    database_url: str = "postgresql+psycopg://speakquest:speakquest@localhost:5433/speakquest"
    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60 * 24

    # Which AI provider answers the player (gemini; see docs/decisions/0001-ai-provider.md).
    # Empty means "not configured": the game stays playable and returns the safe fallback reply.
    ai_provider: str = ""
    ai_api_key: str = ""
    # Provider model names are retired quickly, so the name is a setting; empty uses the default
    ai_model: str = ""
    # One call may take longer than this only if the provider hangs; one retry follows a timeout
    ai_timeout_seconds: float = 20.0

    frontend_dir: Path = DEFAULT_FRONTEND_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
