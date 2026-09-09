"""OAuth verifier contract tests for the installed async MCP TokenVerifier API."""

from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from marketing_mcp.security.oauth import RemoteJWTVerifier

SECRET = "test-only-hmac-secret-at-least-32-bytes"
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
    @pytest.mark.anyio
    async def test_valid_token_accepted_with_scopes(self, verifier):
        access = await verifier.verify_token(_make_token())
        assert access is not None
        assert access.subject == "user-123"
        assert "marketing:read" in access.scopes
        assert "marketing:model" in access.scopes
        assert access.expires_at is not None

    @pytest.mark.anyio
    async def test_expired_token_rejected(self, verifier):
        token = _make_token(exp=int(time.time()) - 3600)
        assert await verifier.verify_token(token) is None

    @pytest.mark.anyio
    async def test_wrong_audience_rejected(self, verifier):
        assert await verifier.verify_token(_make_token(aud="other-api")) is None

    @pytest.mark.anyio
    async def test_wrong_issuer_rejected(self, verifier):
        token = _make_token(iss="https://evil.example.com")
        assert await verifier.verify_token(token) is None

    @pytest.mark.anyio
    async def test_missing_required_scope_rejected(self, verifier):
        token = _make_token(scope="marketing:admin")
        assert await verifier.verify_token(token) is None

    @pytest.mark.anyio
    async def test_no_scope_claim_rejected(self, verifier):
        assert await verifier.verify_token(_make_token(scope=None)) is None

    @pytest.mark.anyio
    async def test_unknown_scope_claim_rejected(self, verifier):
        token = _make_token(scope="marketing:read galactic:dominion")
        assert await verifier.verify_token(token) is None

    @pytest.mark.anyio
    async def test_malformed_token_rejected(self, verifier):
        assert await verifier.verify_token("not.a.jwt") is None
        assert await verifier.verify_token("") is None

    @pytest.mark.anyio
    async def test_wrong_signing_secret_rejected(self, verifier):
        token = _make_token(_secret="attacker-secret-at-least-32-bytes-long")
        assert await verifier.verify_token(token) is None

    def test_remote_jwks_rejects_symmetric_algorithm_configuration(self):
        with pytest.raises(ValueError, match="asymmetric"):
            RemoteJWTVerifier(
                issuer=ISSUER,
                audience=AUDIENCE,
                algorithms=["HS256"],
                jwks_client=object(),
            )

    @pytest.mark.anyio
    async def test_asymmetric_jwks_key_maps_signed_subject_scopes_and_tenant(self):
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(
            {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "sub": "trusted-user",
                "exp": int(time.time()) + 300,
                "scope": "marketing:read marketing:model",
                "organization_id": "tenant-a",
            },
            private_key,
            algorithm="RS256",
            headers={"kid": "current-key"},
        )

        class SigningKey:
            key = private_key.public_key()

        class MockJWKSClient:
            def get_signing_key_from_jwt(self, candidate):
                assert candidate == token
                return SigningKey()

        remote = RemoteJWTVerifier(
            issuer=ISSUER,
            audience=AUDIENCE,
            required_scopes=["marketing:read"],
            algorithms=["RS256"],
            tenant_claim="organization_id",
            require_tenant=True,
            jwks_client=MockJWKSClient(),
        )

        access = await remote.verify_token(token)

        assert access is not None
        assert access.subject == "trusted-user"
        assert access.scopes == ["marketing:read", "marketing:model"]
        assert access.claims["organization_id"] == "tenant-a"
