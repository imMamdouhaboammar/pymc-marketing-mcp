from __future__ import annotations

import os
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from marketing_mcp.errors import DomainError


class SecurityProfile(str, Enum):
    """Deployment security profile (Wave 3 Task 4)."""

    STDIO_LOCAL = "stdio-local"
    HTTP_PRIVATE_API_KEY = "http-private-api-key"
    HTTP_PRODUCTION_OAUTH = "http-production-oauth"

    def validate_http_posture(self, host: str, auth_enabled: bool) -> None:
        """Refuse insecure HTTP deployments before Uvicorn starts."""
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

    # --- Wave 3 Task 4: security profiles ---------------------------------
    security_profile: SecurityProfile = SecurityProfile.STDIO_LOCAL
    api_keys: list[str] = Field(default_factory=list)
    enforce_transport_security: bool = False
    oauth_issuer: str | None = None
    oauth_audience: str | None = None
    oauth_required_scope: str = "marketing:read"

    @model_validator(mode="after")
    def _validate_security_posture(self) -> Settings:
        profile = self.security_profile

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
        if public_bind and http_transport and self.enforce_transport_security and not self.auth_enabled:
            raise DomainError(
                "AUTH_REQUIRED",
                "Refusing to serve HTTP on a public interface without authentication",
                evidence={"host": self.host, "profile": profile.value},
                next_action="Select http-private-api-key or http-production-oauth",
            )
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

        base: dict[str, object] = {
            "data_dir": Path(os.getenv("MARKETING_MCP_DATA_DIR", "data")),
            "ingest_dir": Path(os.getenv("MARKETING_MCP_INGEST_DIR", "inbox")),
            "artifact_dir": Path(os.getenv("MARKETING_MCP_ARTIFACT_DIR", "artifacts")),
            "metadata_db": Path(os.getenv("MARKETING_MCP_METADATA_DB", "metadata.db")),
            "max_dataset_mb": int(os.getenv("MARKETING_MCP_MAX_DATASET_MB", "100")),
            "log_level": os.getenv("MARKETING_MCP_LOG_LEVEL", "INFO"),
            "host": os.getenv("MARKETING_MCP_HOST", os.getenv("HOST", "127.0.0.1")),
            "port": int(os.getenv("MARKETING_MCP_PORT", os.getenv("PORT", "8000"))),
            "auth_enabled": auth_enabled,
            "api_key": api_key,
            "jwt_secret": jwt_secret,
        }
        if profile is not None:
            base["security_profile"] = profile
        return cls(**base)
