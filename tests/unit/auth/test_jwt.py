"""Unit tests for JWT access-token creation and verification.

`backend/auth/jwt.py` is the only place token claims are signed or checked.
Beyond a plain create/decode roundtrip, these tests cover privilege-escalation
attempts against the token itself: forging one with a different (attacker
guessed) key, tampering with a legitimately-issued one, and the standard
expired/malformed failure modes -- all of which must fail closed via
`jose.JWTError`, per `decode_access_token`'s contract.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import JWTError
from jose import jwt as jose_jwt

from backend.auth.jwt import create_access_token, decode_access_token
from backend.config.settings import get_settings
from backend.database.enums import UserRole

settings = get_settings()


def test_roundtrip_preserves_claims() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, role=UserRole.AGENT)

    payload = decode_access_token(token)

    assert payload.sub == str(user_id)
    assert payload.role is UserRole.AGENT


def test_forged_token_with_wrong_signature_key_is_rejected() -> None:
    forged = jose_jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "role": UserRole.ADMIN.value,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "attacker-guessed-secret",
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(JWTError):
        decode_access_token(forged)


def test_tampered_signature_on_a_real_token_is_rejected() -> None:
    token = create_access_token(user_id=uuid.uuid4(), role=UserRole.AGENT)
    last_char = token[-1]
    tampered = token[:-1] + ("A" if last_char != "A" else "B")

    with pytest.raises(JWTError):
        decode_access_token(tampered)


def test_expired_token_is_rejected() -> None:
    token = create_access_token(
        user_id=uuid.uuid4(), role=UserRole.AGENT, expires_delta=timedelta(seconds=-1)
    )

    with pytest.raises(JWTError):
        decode_access_token(token)


def test_malformed_token_raises() -> None:
    with pytest.raises(JWTError):
        decode_access_token("not-a-jwt")
