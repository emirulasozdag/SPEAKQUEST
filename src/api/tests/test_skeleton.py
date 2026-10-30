"""Smoke tests for the project skeleton. Replace stub tests as real features land."""

import pytest


def test_health_reports_api_status(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"ok", "unavailable"}


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/player/progress"),
        ("post", "/api/quests/1/complete"),
        ("post", "/api/dialogue/message"),
        ("get", "/api/story/state"),
    ],
)
def test_planned_endpoints_return_not_implemented(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 501


def test_frontend_is_served_at_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "SpeakQuest" in response.text
