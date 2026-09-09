"""Provider-neutral persistence composition for metadata, jobs, and credentials."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.credentials.repository import CredentialRepository
from marketing_mcp.credentials.sqlite_repository import SQLiteCredentialRepository
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.repository import JobRepository, SQLiteJobRepository
from marketing_mcp.repositories.base import MetadataRepository
from marketing_mcp.storage.metadata import SQLiteMetadataStore


class PersistenceBackend(Protocol):
    @property
    def metadata(self) -> MetadataRepository: ...

    @property
    def jobs(self) -> JobRepository: ...

    @property
    def credentials(self) -> CredentialRepository: ...

    def probe(self) -> None: ...
    def close(self) -> None: ...


class SQLitePersistenceBackend:
    """Local/test backend preserving independent repository connections."""

    def __init__(self, database: Path | str):
        self.metadata = SQLiteMetadataStore(database)
        self.jobs = SQLiteJobRepository(self.metadata.conn)
        self.credentials = SQLiteCredentialRepository(database)

    def probe(self) -> None:
        row = self.metadata.conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        if row is None or row[0] is None:
            raise DomainError("DEPENDENCY_UNAVAILABLE", "Persistence schema is unavailable")

    def close(self) -> None:
        self.credentials.close()
        self.metadata.close()


def build_persistence(settings: Settings) -> PersistenceBackend:
    """Build only an explicitly supported backend; never fall back silently."""
    if settings.persistence_backend == "sqlite":
        if settings.security_profile is SecurityProfile.HTTP_PRODUCTION_OAUTH:
            raise DomainError(
                "CONFIG_INVALID",
                "Production OAuth requires an approved shared SQL persistence backend",
                next_action="Configure the approved shared SQL adapter and URL",
            )
        return SQLitePersistenceBackend(settings.metadata_db)
    raise DomainError(
        "DEPENDENCY_UNAVAILABLE",
        "The shared SQL adapter is not configured in this build",
        next_action="Select and install the owner-approved shared SQL provider adapter",
    )


__all__ = ["PersistenceBackend", "SQLitePersistenceBackend", "build_persistence"]
