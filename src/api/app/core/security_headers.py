"""Security headers on every response, and the Content Security Policy for the frontend.

The access token lives in localStorage, so a script injected into a page could read it. The CSP
is the second line of defence: pages may load scripts only from this server and the pinned
Bootstrap CDN, never inline, and may not be framed by another site. The pages themselves never
put player text into HTML (they use textContent), which is the first line.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Where each kind of resource may come from. Bootstrap is loaded from jsdelivr with a fixed
# version and an integrity hash; the fonts come from Google Fonts.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' https://cdn.jsdelivr.net",
        "style-src 'self' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        # Bootstrap's own CSS draws some icons (menu button, select arrow) as data: SVG images
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# FastAPI's interactive API docs are built with an inline script and a CDN of their own, so they
# keep the other headers but get no CSP
NO_CSP_PATHS = ("/api/docs", "/api/redoc")


class SecurityHeadersMiddleware:
    """Adds SECURITY_HEADERS to every HTTP response, and the CSP to all but NO_CSP_PATHS."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        with_csp = not scope["path"].startswith(NO_CSP_PATHS)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                extra = dict(SECURITY_HEADERS)
                if with_csp:
                    extra["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
                for name, value in extra.items():
                    if name.lower().encode() not in present:
                        headers.append((name.lower().encode(), value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
