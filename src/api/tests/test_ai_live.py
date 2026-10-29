"""One real call to the configured provider. Skipped unless AI_PROVIDER and AI_API_KEY are set.

CI and teammates without a key skip it. If the provider is down or overloaded the test skips
instead of failing, because that says nothing about our code; a wrong answer shape still fails.
"""

import pytest

from app.core.config import get_settings
from app.models.player import EnglishLevel
from app.services.ai.analysis import analyze_message
from app.services.ai.client import build_client
from tests.ai_fakes import job_interview_context

settings = get_settings()

pytestmark = pytest.mark.skipif(
    not (settings.ai_provider and settings.ai_api_key),
    reason="AI_PROVIDER and AI_API_KEY are not set",
)


def test_a_real_reply_for_the_readme_example():
    context = job_interview_context(EnglishLevel.B1)

    result = analyze_message(build_client(settings), context, "Last year I work in a restaurant.")

    if not result.ok and result.reason in {"timeout", "unavailable", "rate_limited", "network"}:
        pytest.skip(f"provider not available right now: {result.reason}")
    assert result.ok, f"unexpected failure: {result.reason}"
    assert result.analysis.communication_success is True
    assert "past_simple" in {error.category.value for error in result.analysis.detected_errors}
    assert result.npc_reply.strip()
