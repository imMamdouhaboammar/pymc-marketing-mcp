import sqlite3

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.jobs.service import JobService
from marketing_mcp.storage.artifacts import LocalArtifactStore
from marketing_mcp.storage.gc import StorageGarbageCollector


def test_storage_gc_sql_syntax_fix(tmp_path):
    """Wave 2: Storage GC must execute SQL without OperationalError and delete expired exports."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE artifact_lifecycle (
            artifact_uri TEXT PRIMARY KEY,
            status TEXT,
            size_bytes INTEGER,
            sha256 TEXT,
            exported_at TEXT,
            created_at TEXT,
            expires_at TEXT
        )
        """
    )
    # Insert one expired and one active
    conn.execute(
        "INSERT INTO artifact_lifecycle VALUES ('blob://test/digest1', 'exported', 100, 'digest1', '2026-01-01', '2026-01-01', '2026-01-02')"
    )
    conn.execute(
        "INSERT INTO artifact_lifecycle VALUES ('blob://test/digest2', 'exported', 200, 'digest2', '2026-01-01', '2026-01-01', '2099-01-01')"
    )
    conn.commit()

    store = LocalArtifactStore(tmp_path)
    gc = StorageGarbageCollector(store, metadata_conn=conn)
    report = gc.cleanup(older_than_hours=0, dry_run=False, clean_tmp=False, force_unreferenced=False)

    assert "errors" not in report or len(report.get("errors", [])) == 0
    # Expired should be deleted from DB
    remaining = conn.execute("SELECT artifact_uri FROM artifact_lifecycle").fetchall()
    assert len(remaining) == 1
    assert remaining[0]["artifact_uri"] == "blob://test/digest2"


def test_job_service_resilience_and_imports():
    """Wave 2: JobService failure paths must raise DomainError cleanly without NameError."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE jobs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT NOT NULL,
            tenant_id TEXT,
            idempotency_key TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            payload TEXT,
            result TEXT,
            error TEXT,
            lease_owner TEXT,
            lease_expires_at TEXT,
            fence_token INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            max_attempts INTEGER DEFAULT 3
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE job_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            progress_percent REAL NOT NULL,
            state_data TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()

    repo = SQLiteJobRepository(conn)
    service = JobService(repo)

    # Resume unknown job must raise DomainError cleanly
    with pytest.raises(DomainError) as exc:
        async def dummy_runner(*_):
            return {}
        service.resume_job("job-unknown", dummy_runner)
    assert exc.value.code in ("JOB_NOT_FOUND", "INVALID_STATE")
