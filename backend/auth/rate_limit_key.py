"""Rate-limit key resolution: authenticated users by user_id, anonymous by IP.

Registered with `backend.core.rate_limit` at startup
(`register_key_resolver`, called from `backend/main.py`) rather than
`core/rate_limit.py` importing `backend.auth.jwt` directly -- see that
module's docstring for why the dependency has to flow this direction.
"""

from __future__ import annotations

from fastapi import Request
from jose import JWTError
from slowapi.util import get_remote_address

from backend.auth.jwt import decode_access_token

_BEARER_PREFIX = "bearer "


def resolve_rate_limit_key(request: Request) -> str:
    """Key by `user:<id>` for a valid bearer token, else `ip:<address>`.

    Never raises: an invalid, expired, or missing token isn't a rate-limit
    concern -- it silently falls back to IP-based keying. The route's own
    `Depends(...)` auth dependency (`backend.auth.dependencies`) is what
    actually enforces authentication; this only affects *which counter* a
    request's hits are tallied against.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith(_BEARER_PREFIX):
        token = auth_header[len(_BEARER_PREFIX) :].strip()
        try:
            payload = decode_access_token(token)
        except JWTError:
            pass
        else:
            return f"user:{payload.sub}"
    return f"ip:{get_remote_address(request)}"
