"""Unit tests for rate-limit key resolution: authenticated users vs anonymous IPs."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import Request

from backend.auth.jwt import create_access_token
from backend.auth.rate_limit_key import resolve_rate_limit_key
from backend.database.enums import UserRole


def _request(headers: dict[str, str]) -> Request:
    raw_headers = [(key.lower().encode(), value.encode()) for key, value in headers.items()]
    scope = {
        "type": "http",
        "headers": raw_headers,
        "client": ("203.0.113.5", 12345),
    }
    return Request(scope)


def test_valid_token_keys_by_user_id() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role=UserRole.AGENT)

    key = resolve_rate_limit_key(_request({"Authorization": f"Bearer {token}"}))

    assert key == f"user:{user_id}"


def test_token_lookup_is_case_insensitive_on_bearer_prefix() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role=UserRole.AGENT)

    key = resolve_rate_limit_key(_request({"Authorization": f"bearer {token}"}))

    assert key == f"user:{user_id}"


def test_no_authorization_header_keys_by_ip() -> None:
    key = resolve_rate_limit_key(_request({}))

    assert key.startswith("ip:")


def test_malformed_authorization_header_keys_by_ip() -> None:
    key = resolve_rate_limit_key(_request({"Authorization": "not-a-bearer-token"}))

    assert key.startswith("ip:")


def test_expired_token_falls_back_to_ip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id, role=UserRole.AGENT, expires_delta=timedelta(seconds=-1)
    )

    key = resolve_rate_limit_key(_request({"Authorization": f"Bearer {token}"}))

    assert key.startswith("ip:")
    assert str(user_id) not in key


def test_garbage_token_falls_back_to_ip() -> None:
    key = resolve_rate_limit_key(_request({"Authorization": "Bearer not-a-real-jwt"}))

    assert key.startswith("ip:")
