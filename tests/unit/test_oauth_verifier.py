"""OAuth verifier contract tests (Wave 3 Task 4) — local signed tokens.

Covers: valid token accepted; expired, wrong-audience, wrong-issuer,
missing-scope, unknown-scope, and malformed tokens rejected (verify_token
returns None per the pinned MCP SDK TokenVerifier contract).
"""

from __future__ import annotations

import time

import jwt
import pytest

from marketing_mcp.security.oauth import RemoteJWTVerifier

SECRET = "test-only-hmac-secret"
ISSUER = "https://issuer.example.com"
AUDIENCE = "pymc-marketing-mcp"


def _make_token(**overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "exp": now + 300,
        "iat": now,
        "scope": "marketing:read marketing:model",
    }
    claims.update(overrides)
    if "scope" in overrides and overrides["scope"] is None:
        claims.pop("scope")
    secret = claims.pop("_secret", SECRET)
    return jwt.encode(claims, secret, algorithm="HS256")


@pytest.fixture
def verifier():
    return RemoteJWTVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        required_scope="marketing:read",
        symmetric_secret=SECRET,
    )


class TestRemoteJWTVerifier:
    def test_valid_token_accepted_with_scopes(self, verifier):
        access = verifier.verify_token(_make_token())
        assert access is not None
        assert access.subject == "user-123"
        assert "marketing:read" in access.scopes
        assert "marketing:model" in access.scopes
        assert access.expires_at is not None

    def test_expired_token_rejected(self, verifier):
        token = _make_token(exp=int(time.time()) - 3600)
        assert verifier.verify_token(token) is None

    def test_wrong_audience_rejected(self, verifier):
        assert verifier.verify_token(_make_token(aud="other-api")) is None

    def test_wrong_issuer_rejected(self, verifier):
        token = _make_token(iss="https://evil.example.com")
        assert verifier.verify_token(token) is None

    def test_missing_required_scope_rejected(self, verifier):
        token = _make_token(scope="marketing:admin")
        assert verifier.verify_token(token) is None

    def test_no_scope_claim_rejected(self, verifier):
        assert verifier.verify_token(_make_token(scope=None)) is None

    def test_unknown_scope_claim_rejected(self, verifier):
        token = _make_token(scope="marketing:read galactic:dominion")
        assert verifier.verify_token(token) is None

    def test_malformed_token_rejected(self, verifier):
        assert verifier.verify_token("not.a.jwt") is None
        assert verifier.verify_token("") is None

    def test_wrong_signing_secret_rejected(self, verifier):
        token = _make_token(_secret="attacker-secret")
        assert verifier.verify_token(token) is None
