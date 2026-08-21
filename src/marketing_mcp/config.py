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

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("MARKETING_MCP_DATA_DIR","data")),
            ingest_dir=Path(os.getenv("MARKETING_MCP_INGEST_DIR","inbox")),
            artifact_dir=Path(os.getenv("MARKETING_MCP_ARTIFACT_DIR","artifacts")),
            metadata_db=Path(os.getenv("MARKETING_MCP_METADATA_DB","metadata.db")),
            max_dataset_mb=int(os.getenv("MARKETING_MCP_MAX_DATASET_MB","100")),
            log_level=os.getenv("MARKETING_MCP_LOG_LEVEL","INFO"),
            host=os.getenv("MARKETING_MCP_HOST","127.0.0.1"),
            port=int(os.getenv("MARKETING_MCP_PORT","8000")),
        )
