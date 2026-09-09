"""Production OAuth settings and active AuthManager composition contracts."""

from __future__ import annotations

from mcp.server.auth.provider import AccessToken
from starlette.datastructures import Headers, QueryParams

from marketing_mcp.auth import AuthManager
from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.security.oauth import RemoteJWTVerifier


def _production_settings() -> Settings:
    return Settings(
        security_profile=SecurityProfile.HTTP_PRODUCTION_OAUTH,
        oauth_issuer="https://issuer.example.com/",
        oauth_audience="pymc-marketing-mcp",
        oauth_jwks_url="https://keys.example.com/oauth/jwks.json",
        oauth_required_scopes=["marketing:read", "marketing:model"],
        oauth_algorithms=["RS256", "ES256"],
        oauth_tenant_claim="org_id",
    )


def test_settings_from_env_loads_complete_oauth_configuration(monkeypatch):
    monkeypatch.setenv("MARKETING_MCP_SECURITY_PROFILE", "http-production-oauth")
    monkeypatch.setenv("MARKETING_MCP_OAUTH_ISSUER", "https://issuer.example.com/")
    monkeypatch.setenv("MARKETING_MCP_OAUTH_AUDIENCE", "pymc-marketing-mcp")
    monkeypatch.setenv("MARKETING_MCP_OAUTH_JWKS_URL", "https://keys.example.com/jwks.json")
    monkeypatch.setenv(
        "MARKETING_MCP_OAUTH_REQUIRED_SCOPES", "marketing:read, marketing:model"
    )
    monkeypatch.setenv("MARKETING_MCP_OAUTH_ALGORITHMS", "RS256,ES256")
    monkeypatch.setenv("MARKETING_MCP_OAUTH_TENANT_CLAIM", "organization_id")

    settings = Settings.from_env()

    assert settings.oauth_issuer == "https://issuer.example.com/"
    assert settings.oauth_audience == "pymc-marketing-mcp"
    assert settings.oauth_jwks_url == "https://keys.example.com/jwks.json"
    assert settings.oauth_required_scopes == ["marketing:read", "marketing:model"]
    assert settings.oauth_algorithms == ["RS256", "ES256"]
    assert settings.oauth_tenant_claim == "organization_id"
    assert settings.auth_enabled is True


def test_production_composition_selects_remote_jwks_verifier():
    manager = AuthManager.from_settings(_production_settings())

    assert manager.enabled is True
    assert isinstance(manager.bearer_token_verifier, RemoteJWTVerifier)
    assert manager.bearer_token_verifier.jwks_url == "https://keys.example.com/oauth/jwks.json"
    assert manager.bearer_token_verifier.algorithms == ("RS256", "ES256")
    assert manager.jwt_validator.secret is None


def test_production_remote_verifier_failure_fails_closed():
    manager = AuthManager.from_settings(_production_settings())

    class UnavailableJWKS:
        def get_signing_key_from_jwt(self, _token):
            raise OSError("issuer unavailable")

    manager.bearer_token_verifier._jwks_client = UnavailableJWKS()
    result = manager.authenticate(
        Headers({"authorization": "Bearer header.payload.signature"}), QueryParams()
    )

    assert result.authenticated is False
    assert "issuer unavailable" not in (result.error_message or "")


def test_verified_oauth_claims_map_only_from_trusted_verifier_output():
    class TrustedVerifier:
        tenant_claim = "org_id"

        def verify(self, token: str) -> AccessToken | None:
            assert token == "signed-token"
            return AccessToken(
                token=token,
                client_id="untrusted-client-alias",
                subject="trusted-subject",
                scopes=["marketing:read"],
                claims={"sub": "trusted-subject", "org_id": "tenant-a"},
            )

    manager = AuthManager(enabled=True, bearer_token_verifier=TrustedVerifier())
    result = manager.authenticate(
        Headers({"authorization": "Bearer signed-token"}), QueryParams()
    )

    assert result.authenticated is True
    assert result.auth_type == "jwt"
    assert result.client_id == "trusted-subject"
    assert result.scopes == ["marketing:read"]
    assert result.tenant_id == "tenant-a"
