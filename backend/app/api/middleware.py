"""Security middleware, written as plain ASGI so it runs before any request parsing."""

import json
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
BODY_METHODS = {"POST", "PUT", "PATCH"}


async def _send_json(send: Send, status: int, payload: dict, extra_headers: list[tuple[bytes, bytes]] | None = None) -> None:
    body = json.dumps(payload).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    headers += extra_headers or []
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return None


class SecurityHeadersMiddleware:
    """Adds protective headers to every response, and no-store to every API response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-resource-policy", b"same-site"),
                ]
                if scope["path"].startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


class CsrfOriginMiddleware:
    """CSRF protection (second layer after SameSite cookies).

    State-changing API requests must:
    - carry an Origin header from an allowed origin (browsers always send it on POST/PUT/PATCH/DELETE);
    - send JSON, which HTML forms on other sites cannot do without a CORS preflight.
    """

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.allowed = settings.allowed_origins

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS or not scope["path"].startswith("/api/"):
            return await self.app(scope, receive, send)

        origin = _header(scope, b"origin")
        if not origin:
            return await _send_json(send, 403, {"error": "Request origin not allowed."})
        parts = urlsplit(origin)
        if f"{parts.scheme}://{parts.netloc}" not in self.allowed:
            return await _send_json(send, 403, {"error": "Request origin not allowed."})

        if scope["method"] in BODY_METHODS:
            content_type = (_header(scope, b"content-type") or "").lower()
            if not content_type.startswith("application/json"):
                return await _send_json(send, 415, {"error": "Expected application/json."})

        await self.app(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Rejects request bodies over the limit, including chunked bodies with no Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        declared = _header(scope, b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            return await _send_json(send, 413, {"error": "Request body too large."})

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge()
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            if not response_started:
                await _send_json(send, 413, {"error": "Request body too large."})
