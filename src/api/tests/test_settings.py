"""Settings: the secret key check and the settings that reach the Docker container (#62)."""

import logging
import re
from pathlib import Path

import pytest

from app.core.config import (
    DEFAULT_SECRET_KEY,
    EXAMPLE_SECRET_KEY,
    InsecureSecretKeyError,
    Settings,
    check_secret_key,
    secret_key_problem,
)

ROOT = Path(__file__).resolve().parents[3]
GOOD_KEY = "k" * 48
LOGGER = logging.getLogger("speakquest.test")


@pytest.mark.parametrize("key", [DEFAULT_SECRET_KEY, EXAMPLE_SECRET_KEY, "short-but-random"])
def test_unsafe_keys_are_recognised(key):
    assert secret_key_problem(Settings(secret_key=key)) is not None


def test_a_long_random_key_is_fine():
    assert secret_key_problem(Settings(secret_key=GOOD_KEY)) is None


@pytest.mark.parametrize("key", [DEFAULT_SECRET_KEY, EXAMPLE_SECRET_KEY, "short-but-random"])
def test_outside_development_an_unsafe_key_stops_the_app_without_showing_the_key(key):
    with pytest.raises(InsecureSecretKeyError) as error:
        check_secret_key(Settings(environment="production", secret_key=key), LOGGER)

    message = str(error.value)
    assert key not in message
    assert "secrets.token_urlsafe" in message
    assert "ENVIRONMENT=production" in message


def test_in_development_an_unsafe_key_is_only_a_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="speakquest.test"):
        check_secret_key(Settings(environment="development", secret_key=DEFAULT_SECRET_KEY), LOGGER)

    assert len(caplog.records) == 1
    assert DEFAULT_SECRET_KEY not in caplog.text


def test_a_good_key_passes_silently_in_production(caplog):
    with caplog.at_level(logging.WARNING, logger="speakquest.test"):
        check_secret_key(Settings(environment="production", secret_key=GOOD_KEY), LOGGER)

    assert caplog.records == []


# --- every documented setting reaches the container ---------------------------------------------

# Used by docker-compose itself (database container) or replaced by the URL compose builds
COMPOSE_ONLY = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "POSTGRES_PORT", "DATABASE_URL"}


def example_settings() -> set[str]:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Z][A-Z0-9_]+)=", text, re.MULTILINE)) - COMPOSE_ONLY


def api_environment() -> dict[str, str]:
    """The api service's environment block in docker-compose.yml, as name -> default."""
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    block = text.split("  api:", 1)[1].split("    ports:", 1)[0]
    return dict(re.findall(r"^\s{6}([A-Z][A-Z0-9_]+): \$\{[A-Z0-9_]+:-([^}]*)\}", block, re.MULTILINE))


def test_every_setting_in_env_example_is_passed_to_the_api_container():
    assert example_settings() - set(api_environment()) == set()


def test_every_setting_in_env_example_is_a_real_setting():
    fields = {name.upper() for name in Settings.model_fields}

    assert example_settings() - fields == set()


@pytest.mark.parametrize("name", sorted(set(api_environment()) - {"SECRET_KEY", "AI_PROVIDER", "AI_API_KEY", "AI_MODEL"}))
def test_container_defaults_match_the_app_defaults(name):
    default = Settings.model_fields[name.lower()].default
    in_compose = api_environment()[name]

    if isinstance(default, (int, float)):
        assert float(in_compose) == default
    else:
        assert in_compose == str(default)
