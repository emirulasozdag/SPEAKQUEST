"""Security headers and the Content Security Policy (#77)."""

import re
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.security_headers import CONTENT_SECURITY_POLICY, SECURITY_HEADERS

FRONTEND = get_settings().frontend_dir


@pytest.mark.parametrize("path", ["/", "/pages/dialogue.html", "/css/main.css", "/api/health", "/api/no-such-thing"])
def test_every_response_has_the_security_headers_and_the_csp(client, path):
    response = client.get(path)

    for name, value in SECURITY_HEADERS.items():
        assert response.headers[name] == value
    assert response.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY


def test_error_responses_have_them_too(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers


def test_the_api_docs_keep_working_without_the_csp(client):
    response = client.get("/api/docs")

    assert response.status_code == 200
    assert "Content-Security-Policy" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_only_this_site_may_use_the_microphone(client):
    policy = client.get("/pages/dialogue.html").headers["Permissions-Policy"]

    assert "microphone=(self)" in policy
    assert "camera=()" in policy


def test_the_policy_allows_no_inline_scripts_and_no_framing():
    directives = dict(part.split(" ", 1) for part in CONTENT_SECURITY_POLICY.split("; "))

    assert "'unsafe-inline'" not in CONTENT_SECURITY_POLICY
    assert "'unsafe-eval'" not in CONTENT_SECURITY_POLICY
    assert directives["frame-ancestors"] == "'none'"
    assert directives["object-src"] == "'none'"
    assert directives["script-src"] == "'self' https://cdn.jsdelivr.net"


def frontend_files(*suffixes: str) -> list[Path]:
    return [path for path in FRONTEND.rglob("*") if path.suffix in suffixes]


@pytest.mark.parametrize("path", frontend_files(".html"), ids=lambda path: path.name)
def test_pages_have_no_inline_scripts_styles_or_handlers(path):
    """The CSP blocks these, so a page using them would break silently in the browser."""
    html = path.read_text(encoding="utf-8")

    inline_scripts = [tag for tag in re.findall(r"<script\b[^>]*>", html) if "src=" not in tag]
    assert inline_scripts == []
    assert not re.search(r"<style\b", html)
    assert not re.search(r"\sstyle=\"", html)
    assert not re.search(r"\son[a-z]+=\"", html)


@pytest.mark.parametrize("path", frontend_files(".js"), ids=lambda path: path.name)
def test_scripts_write_no_inline_styles_or_handlers_into_html(path):
    source = path.read_text(encoding="utf-8")

    assert not re.search(r"\sstyle=\"", source)
    assert not re.search(r"\son[a-z]+=\"", source)
