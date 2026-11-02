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

    # Dialogue messages one player may send inside the window; the next one gets 429. It protects
    # the AI quota (the free Gemini tier allows only a few requests per minute) from one player
    dialogue_rate_limit: int = 10
    dialogue_rate_window_seconds: int = 60

    # Failed logins allowed per email + IP inside the window; the next attempt gets 429
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 60
    # Registration attempts allowed per IP inside the window
    register_rate_limit: int = 5
    register_rate_window_seconds: int = 60
    # Wrong current passwords allowed per account inside the window, for changing the password and
    # deleting the account; someone holding a stolen session cannot guess the password endlessly
    password_check_rate_limit: int = 5
    password_check_rate_window_seconds: int = 900

    frontend_dir: Path = DEFAULT_FRONTEND_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
