"""Auth stub and the local-access guard."""

import ipaddress
from urllib.parse import urlsplit

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from explorator.config import settings


class AuthStubMiddleware(BaseHTTPMiddleware):
    """Stub auth middleware. v1 is single-user, no auth required.

    TODO: Implement auth for multi-user support.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        return await call_next(request)


_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _hostname(netloc: str) -> str:
    """Hostname part of a ``host[:port]`` value, lower-cased, IPv6 brackets removed.

    Malformed values yield "" (never allowed).
    """
    try:
        return (urlsplit(f"//{netloc}").hostname or "").lower()
    except ValueError:
        return ""


def _netloc(url: str) -> str:
    """``host[:port]`` of a URL such as an Origin header; "" when malformed."""
    try:
        return urlsplit(url).netloc.lower()
    except ValueError:
        return ""


def _host_allowed(hostname: str, extra: set[str]) -> bool:
    if "*" in extra or hostname in extra:
        return True
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True  # DNS rebinding needs a hostname, so IP literals are safe to admit


class LocalAccessGuard:
    """Keep other websites from driving the API through the user's browser.

    The API has no auth (ADR-010), so two browser-borne attacks matter:

    - DNS rebinding: a hostile domain re-resolves to 127.0.0.1 and becomes
      same-origin with the API. Blocked by admitting only localhost, IP
      literals and ``ALLOWED_HOSTS`` in the Host header.
    - Cross-site requests: a hostile page POSTs to localhost. Blocked by
      rejecting state-changing requests whose Origin is neither the request's
      own host (directly, or ``X-Forwarded-Host`` from the Vite/nginx proxy,
      which must itself be an allowed host) nor an allowed host. There is no
      CORS middleware, so cross-origin responses stay unreadable and
      preflighted requests fail.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        extra = {h.strip().lower() for h in settings.allowed_hosts.split(",") if h.strip()}
        host = headers.get("host", "")

        if not _host_allowed(_hostname(host), extra):
            response = PlainTextResponse(
                "Host not allowed. Add it to ALLOWED_HOSTS to serve this API under that name.",
                status_code=400,
            )
            await response(scope, receive, send)
            return

        origin = headers.get("origin")
        if scope["method"] not in _SAFE_METHODS and origin is not None:
            origin_netloc = _netloc(origin)
            forwarded = headers.get("x-forwarded-host", "").lower()
            own = {host.lower()}
            if forwarded and _host_allowed(_hostname(forwarded), extra):
                own.add(forwarded)
            own.discard("")
            if not origin_netloc or origin_netloc not in own and not (
                "*" in extra or _hostname(origin_netloc) in extra
            ):
                response = PlainTextResponse("Cross-site request blocked.", status_code=403)
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
