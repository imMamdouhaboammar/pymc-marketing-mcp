from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from marketing_mcp.errors import DomainError


class SecurityProfile(str, Enum):
    """Deployment security profile (Wave 3 Task 4)."""

    STDIO_LOCAL = "stdio-local"
    HTTP_PRIVATE_API_KEY = "http-private-api-key"
    HTTP_PRODUCTION_OAUTH = "http-production-oauth"

    def validate_http_posture(self, host: str, auth_enabled: bool) -> None:
        """Refuse insecure HTTP deployments before Uvicorn starts."""
        if os.getenv("MARKETING_MCP_ALLOW_ANONYMOUS_HTTP", "").lower() in ("true", "1", "yes"):
            return
        if self is self.STDIO_LOCAL:
            public_bind = host not in ("127.0.0.1", "localhost", "::1")
            if public_bind and not auth_enabled:
                raise DomainError(
                    "AUTH_REQUIRED",
                    "Refusing to serve HTTP on a public interface without authentication",
                    evidence={"host": host, "profile": self.value},
                    next_action="Select http-private-api-key or http-production-oauth",
                )
            return
        if not auth_enabled:
            raise DomainError(
                "AUTH_REQUIRED",
                f"Profile '{self.value}' requires authentication to serve HTTP",
                evidence={"profile": self.value},
                next_action="Configure credentials before startup",
            )


class Settings(BaseModel):
    data_dir: Path = Field(default=Path("data"))
    ingest_dir: Path = Field(default=Path("inbox"))
    artifact_dir: Path = Field(default=Path("artifacts"))
    metadata_db: Path = Field(default=Path("metadata.db"))
    max_dataset_mb: int = 100
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    transport: str = "stdio"
    auth_enabled: bool = False
    api_key: str | None = None
    jwt_secret: str | None = None
    jwt_issuer: str = "pymc-marketing-mcp"
    jwt_audience: str = "mcp-clients"

    # --- Wave 3 Task 4: security profiles ---------------------------------
    security_profile: SecurityProfile = SecurityProfile.STDIO_LOCAL
    api_keys: list[str] = Field(default_factory=list)
    enforce_transport_security: bool = False
    oauth_issuer: str | None = None
    oauth_audience: str | None = None
    oauth_jwks_url: str | None = None
    oauth_required_scope: str = "marketing:read"
    oauth_required_scopes: list[str] = Field(default_factory=lambda: ["marketing:read"])
    oauth_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    oauth_tenant_claim: str = "tenant_id"
    oauth_require_tenant: bool = True
    job_execution_mode: str | None = None
    persistence_backend: str = "sqlite"
    shared_sql_url: str | None = None
    rate_limit_per_minute: int = 120

    # --- Phase 7: Platform Client & Gateway Bridge ---
    gateway_url: str = "http://127.0.0.1:8080"
    organization_id: str | None = None
    principal_id: str | None = None
    principal_role: str = "analyst"
    platform_client_enabled: bool = False

    @model_validator(mode="after")
    def _validate_security_posture(self) -> Settings:
        profile = self.security_profile
        if self.persistence_backend not in {"sqlite", "shared-sql"}:
            raise DomainError(
                "CONFIG_INVALID", "persistence_backend must be 'sqlite' or 'shared-sql'"
            )
        if self.persistence_backend == "shared-sql" and not self.shared_sql_url:
            raise DomainError(
                "CONFIG_INVALID", "shared-sql persistence requires shared_sql_url"
            )
        if self.persistence_backend == "sqlite" and self.shared_sql_url:
            raise DomainError(
                "CONFIG_INVALID", "shared_sql_url cannot be ignored by sqlite persistence"
            )
        if self.job_execution_mode not in {None, "in-process", "enqueue-only"}:
            raise DomainError(
                "CONFIG_INVALID",
                "job_execution_mode must be 'in-process' or 'enqueue-only'",
            )
        if profile is SecurityProfile.HTTP_PRODUCTION_OAUTH:
            self.job_execution_mode = "enqueue-only"
        elif self.job_execution_mode is None:
            self.job_execution_mode = "in-process"

        if profile is SecurityProfile.HTTP_PRODUCTION_OAUTH:
            if not self.oauth_issuer or not self.oauth_audience:
                raise DomainError(
                    "CONFIG_INVALID",
                    "http-production-oauth requires oauth_issuer and oauth_audience",
                    evidence={
                        "oauth_issuer": bool(self.oauth_issuer),
                        "oauth_audience": bool(self.oauth_audience),
                    },
                    next_action="Configure the OAuth issuer and audience before startup",
                )
            allowed_algorithms = {
                "RS256",
                "RS384",
                "RS512",
                "PS256",
                "PS384",
                "PS512",
                "ES256",
                "ES384",
                "ES512",
                "EdDSA",
            }
            if not self.oauth_algorithms or not set(self.oauth_algorithms) <= allowed_algorithms:
                raise DomainError(
                    "CONFIG_INVALID",
                    "Production OAuth requires explicitly allowed asymmetric signing algorithms",
                    evidence={"oauth_algorithms": self.oauth_algorithms},
                    next_action="Configure one or more asymmetric OAuth signing algorithms",
                )
            if not self.oauth_required_scopes or not self.oauth_tenant_claim.strip():
                raise DomainError(
                    "CONFIG_INVALID",
                    "Production OAuth requires scopes and a trusted tenant claim mapping",
                    next_action="Configure OAuth required scopes and tenant claim name",
                )
            if self.oauth_jwks_url is None:
                self.oauth_jwks_url = f"{self.oauth_issuer.rstrip('/')}/.well-known/jwks.json"
            self.auth_enabled = True
            return self

        if profile is SecurityProfile.HTTP_PRIVATE_API_KEY:
            if not (self.api_keys or self.api_key):
                raise DomainError(
                    "AUTH_REQUIRED",
                    "http-private-api-key requires at least one configured API key",
                    next_action="Set MARKETING_MCP_API_KEY before startup",
                )
            return self

        # stdio-local: refuse public HTTP binding without explicit opt-in.
        public_bind = self.host not in ("127.0.0.1", "localhost", "::1")
        http_transport = self.transport != "stdio"
        allow_anonymous = os.getenv("MARKETING_MCP_ALLOW_ANONYMOUS_HTTP", "").lower() in ("true", "1", "yes")
        if public_bind and http_transport and self.enforce_transport_security and not self.auth_enabled and not allow_anonymous:
            raise DomainError(
                "AUTH_REQUIRED",
                "Refusing to serve HTTP on a public interface without authentication",
                evidence={"host": self.host, "profile": profile.value},
                next_action="Select http-private-api-key or http-production-oauth",
            )
        if self.rate_limit_per_minute <= 0:
            raise DomainError(
                "CONFIG_INVALID",
                f"rate_limit_per_minute must be greater than zero, got {self.rate_limit_per_minute}",
            )

        # Canonicalize filesystem paths to absolute paths
        self.data_dir = self.data_dir.expanduser().resolve()
        self.ingest_dir = self.ingest_dir.expanduser().resolve()
        self.artifact_dir = self.artifact_dir.expanduser().resolve()
        self.metadata_db = self.metadata_db.expanduser().resolve()
        self.metadata_db.parent.mkdir(parents=True, exist_ok=True)

        return self

    @classmethod
    def from_env(cls):
        api_key = os.getenv("MARKETING_MCP_API_KEY", "").strip() or None
        jwt_secret = os.getenv("MARKETING_MCP_JWT_SECRET", "").strip() or None
        auth_enabled_env = os.getenv("MARKETING_MCP_AUTH_ENABLED", "").strip().lower()
        if auth_enabled_env in ("1", "true", "yes"):
            auth_enabled = True
        elif auth_enabled_env in ("0", "false", "no"):
            auth_enabled = False
        else:
            auth_enabled = bool(api_key or jwt_secret)

        profile_raw = os.getenv("MARKETING_MCP_SECURITY_PROFILE", "").strip()
        profile = SecurityProfile(profile_raw) if profile_raw else None
        api_keys = [value.strip() for value in (api_key or "").split(",") if value.strip()]
        oauth_required_scopes = [
            value.strip()
            for value in os.getenv(
                "MARKETING_MCP_OAUTH_REQUIRED_SCOPES", "marketing:read"
            ).split(",")
            if value.strip()
        ]
        oauth_algorithms = [
            value.strip()
            for value in os.getenv("MARKETING_MCP_OAUTH_ALGORITHMS", "RS256").split(",")
            if value.strip()
        ]
        oauth_require_tenant = os.getenv(
            "MARKETING_MCP_OAUTH_REQUIRE_TENANT", "true"
        ).strip().lower() in ("1", "true", "yes")

        rate_limit_raw = os.getenv("MARKETING_MCP_RATE_LIMIT_PER_MINUTE", "120").strip()
        try:
            rate_limit_val = int(rate_limit_raw)
        except ValueError as exc:
            raise DomainError(
                "CONFIG_INVALID",
                f"MARKETING_MCP_RATE_LIMIT_PER_MINUTE must be an integer, got '{rate_limit_raw}'",
            ) from exc
        if rate_limit_val <= 0:
            raise DomainError(
                "CONFIG_INVALID",
                f"MARKETING_MCP_RATE_LIMIT_PER_MINUTE must be greater than zero, got {rate_limit_val}",
            )

        base: dict[str, Any] = {
            "data_dir": Path(os.getenv("MARKETING_MCP_DATA_DIR", "data")),
            "ingest_dir": Path(os.getenv("MARKETING_MCP_INGEST_DIR", "inbox")),
            "artifact_dir": Path(os.getenv("MARKETING_MCP_ARTIFACT_DIR", "artifacts")),
            "metadata_db": Path(os.getenv("MARKETING_MCP_METADATA_DB", "metadata.db")),
            "max_dataset_mb": int(os.getenv("MARKETING_MCP_MAX_DATASET_MB", "100")),
            "log_level": os.getenv("MARKETING_MCP_LOG_LEVEL", "INFO"),
            "host": os.getenv("MARKETING_MCP_HOST", os.getenv("HOST", "127.0.0.1")),
            "port": int(os.getenv("MARKETING_MCP_PORT", os.getenv("PORT", "8000"))),
            "transport": os.getenv("MARKETING_MCP_TRANSPORT", "stdio"),
            "auth_enabled": auth_enabled,
            "api_key": api_key,
            "api_keys": api_keys,
            "jwt_secret": jwt_secret,
            "jwt_issuer": os.getenv("MARKETING_MCP_JWT_ISSUER", "pymc-marketing-mcp"),
            "jwt_audience": os.getenv("MARKETING_MCP_JWT_AUDIENCE", "mcp-clients"),
            "oauth_issuer": os.getenv("MARKETING_MCP_OAUTH_ISSUER", "").strip() or None,
            "oauth_audience": os.getenv("MARKETING_MCP_OAUTH_AUDIENCE", "").strip() or None,
            "oauth_jwks_url": os.getenv("MARKETING_MCP_OAUTH_JWKS_URL", "").strip() or None,
            "oauth_required_scopes": oauth_required_scopes,
            "oauth_algorithms": oauth_algorithms,
            "oauth_tenant_claim": os.getenv(
                "MARKETING_MCP_OAUTH_TENANT_CLAIM", "tenant_id"
            ).strip(),
            "oauth_require_tenant": oauth_require_tenant,
            "job_execution_mode": os.getenv("MARKETING_MCP_JOB_EXECUTION_MODE", "").strip()
            or None,
            "persistence_backend": os.getenv(
                "MARKETING_MCP_PERSISTENCE_BACKEND", "sqlite"
            ).strip(),
            "shared_sql_url": os.getenv("MARKETING_MCP_SHARED_SQL_URL", "").strip() or None,
            "rate_limit_per_minute": rate_limit_val,
            "gateway_url": os.getenv("MARKETING_MCP_GATEWAY_URL", "http://127.0.0.1:8080"),
            "organization_id": os.getenv("MARKETING_MCP_ORGANIZATION_ID", "").strip() or None,
            "principal_id": os.getenv("MARKETING_MCP_PRINCIPAL_ID", "").strip() or None,
            "principal_role": os.getenv("MARKETING_MCP_PRINCIPAL_ROLE", "analyst").strip(),
            "platform_client_enabled": os.getenv("MARKETING_MCP_PLATFORM_CLIENT_ENABLED", "false").strip().lower() in ("1", "true", "yes"),
        }
        if profile is not None:
            base["security_profile"] = profile
        return cls(**base)
