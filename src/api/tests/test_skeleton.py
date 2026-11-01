"""Smoke tests for the project skeleton. Replace stub tests as real features land."""


def test_health_reports_api_status(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] in {"ok", "unavailable"}


def test_frontend_is_served_at_root(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "SpeakQuest" in response.text
