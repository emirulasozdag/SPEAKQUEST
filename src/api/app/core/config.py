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

    ai_provider: str = ""
    ai_api_key: str = ""

    frontend_dir: Path = DEFAULT_FRONTEND_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
