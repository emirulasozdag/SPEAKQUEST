"""Smoke tests for the project skeleton. Replace stub tests as real features land."""

from app.core.config import get_settings


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


def test_the_privacy_page_is_public_and_says_what_matters(client):
    """#69: what is stored, that messages go to an AI service, and how to delete everything."""
    response = client.get("/pages/privacy.html")

    assert response.status_code == 200
    for words in ("Do not type real personal information", "Google Gemini", "Delete account", "Reset game progress"):
        assert words in response.text
    assert 'data-auth="required"' not in response.text


def test_the_ai_warning_is_shown_where_players_sign_up_and_type():
    pages = get_settings().frontend_dir / "pages"
    for page in ("register.html", "dialogue.html"):
        html = (pages / page).read_text(encoding="utf-8")
        assert "Don't type real personal information" in html
        assert 'href="/pages/privacy.html"' in html
    footer = (get_settings().frontend_dir / "js" / "components" / "footer.js").read_text(encoding="utf-8")
    assert 'href="/pages/privacy.html"' in footer
