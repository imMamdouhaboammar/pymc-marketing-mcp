"""Security profile configuration (Wave 3 Task 4).

Profiles:
- stdio-local: trusted local transport; every scope granted.
- http-private-api-key: explicit private deployment with shared API keys.
- http-production-oauth: OAuth 2.1 resource server; fails closed without a
  configured token verifier.

Fail-closed rule: binding HTTP to a non-loopback host requires either the
private API-key profile with at least one key, or the production OAuth
profile with verifier configuration. Misconfiguration refuses startup before
Uvicorn starts.
"""

from __future__ import annotations

import pytest

from marketing_mcp.config import Settings


class TestProfileEnum:
    def test_profile_values(self):
        from marketing_mcp.config import SecurityProfile

        assert {p.value for p in SecurityProfile} == {
            "stdio-local",
            "http-private-api-key",
            "http-production-oauth",
        }

    def test_default_profile_is_stdio_local(self):
        s = Settings(data_dir="d", artifact_dir="a", metadata_db="m.db", ingest_dir="i")
        assert s.security_profile == "stdio-local"

    def test_explicit_profile_accepted(self):
        s = Settings(
            data_dir="d",
            artifact_dir="a",
            metadata_db="m.db",
            ingest_dir="i",
            security_profile="http-private-api-key",
            auth_enabled=True,
            api_keys=["k1"],
        )
        assert s.security_profile == "http-private-api-key"

    def test_profile_from_env(self, monkeypatch):
        monkeypatch.setenv("MARKETING_MCP_SECURITY_PROFILE", "http-private-api-key")
        monkeypatch.setenv("MARKETING_MCP_API_KEY", "k1")
        s = Settings.model_validate(Settings.from_env().model_dump())
        assert s.security_profile == "http-private-api-key"


class TestFailClosed:
    def test_production_oauth_without_verifier_refuses_startup(self):
        from marketing_mcp.errors import DomainError

        with pytest.raises(DomainError) as exc_info:
            Settings(
                data_dir="d",
                artifact_dir="a",
                metadata_db="m.db",
                ingest_dir="i",
                security_profile="http-production-oauth",
                auth_enabled=True,
            )
        assert exc_info.value.code in ("AUTH_REQUIRED", "CONFIG_INVALID")

    def test_public_bind_without_auth_refuses_startup(self):
        from marketing_mcp.errors import DomainError

        with pytest.raises(DomainError):
            Settings(
                data_dir="d",
                artifact_dir="a",
                metadata_db="m.db",
                ingest_dir="i",
                host="0.0.0.0",
                transport="streamable-http",
                auth_enabled=False,
                enforce_transport_security=True,
            )

    def test_private_api_key_profile_requires_at_least_one_key(self):
        from marketing_mcp.errors import DomainError

        with pytest.raises(DomainError):
            Settings(
                data_dir="d",
                artifact_dir="a",
                metadata_db="m.db",
                ingest_dir="i",
                security_profile="http-private-api-key",
                auth_enabled=True,
            )

    def test_valid_production_oauth_profile_accepted(self):
        s = Settings(
            data_dir="d",
            artifact_dir="a",
            metadata_db="m.db",
            ingest_dir="i",
            security_profile="http-production-oauth",
            auth_enabled=True,
            oauth_issuer="https://issuer.example.com",
            oauth_audience="pymc-marketing-mcp",
        )
        assert s.oauth_issuer == "https://issuer.example.com"


class TestHttpPostureGate:
    def test_stdio_profile_refuses_public_http_without_auth(self):
        from marketing_mcp.config import SecurityProfile
        from marketing_mcp.errors import DomainError

        with pytest.raises(DomainError) as exc_info:
            SecurityProfile.STDIO_LOCAL.validate_http_posture("0.0.0.0", auth_enabled=False)
        assert exc_info.value.code == "AUTH_REQUIRED"

    def test_production_oauth_requires_auth(self):
        from marketing_mcp.config import SecurityProfile
        from marketing_mcp.errors import DomainError

        with pytest.raises(DomainError):
            SecurityProfile.HTTP_PRODUCTION_OAUTH.validate_http_posture(
                "127.0.0.1", auth_enabled=False
            )
