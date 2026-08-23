from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    data_dir: Path = Field(default=Path("data"))
    ingest_dir: Path = Field(default=Path("inbox"))
    artifact_dir: Path = Field(default=Path("artifacts"))
    metadata_db: Path = Field(default=Path("metadata.db"))
    max_dataset_mb: int = 100
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
    auth_enabled: bool = False
    api_key: str | None = None
    jwt_secret: str | None = None

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

        return cls(
            data_dir=Path(os.getenv("MARKETING_MCP_DATA_DIR", "data")),
            ingest_dir=Path(os.getenv("MARKETING_MCP_INGEST_DIR", "inbox")),
            artifact_dir=Path(os.getenv("MARKETING_MCP_ARTIFACT_DIR", "artifacts")),
            metadata_db=Path(os.getenv("MARKETING_MCP_METADATA_DB", "metadata.db")),
            max_dataset_mb=int(os.getenv("MARKETING_MCP_MAX_DATASET_MB", "100")),
            log_level=os.getenv("MARKETING_MCP_LOG_LEVEL", "INFO"),
            host=os.getenv("MARKETING_MCP_HOST", os.getenv("HOST", "127.0.0.1")),
            port=int(os.getenv("MARKETING_MCP_PORT", os.getenv("PORT", "8000"))),
            auth_enabled=auth_enabled,
            api_key=api_key,
            jwt_secret=jwt_secret,
        )
