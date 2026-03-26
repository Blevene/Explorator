"""Auth and middleware stubs."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class AuthStubMiddleware(BaseHTTPMiddleware):
    """Stub auth middleware. v1 is single-user, no auth required.

    TODO: Implement auth for multi-user support.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        return await call_next(request)
