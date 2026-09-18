"""Schema migrations manager for SQLite metadata storage."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Connection], None]]] = []


def migration(version: int, name: str):
    def decorator(fn: Callable[[sqlite3.Connection], None]):
        MIGRATIONS.append((version, name, fn))
        MIGRATIONS.sort(key=lambda x: x[0])
        return fn

    return decorator


@migration(1, "initial_core_tables")
def migrate_001_initial(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS datasets (
            dataset_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS models (
            model_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scenarios (
            scenario_id TEXT PRIMARY KEY,
            model_id TEXT,
            payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS clv_models (
            model_id TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        """
    )


@migration(2, "add_jobs_and_indices")
def migrate_002_jobs(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            owner TEXT NOT NULL DEFAULT 'local',
            tenant_id TEXT,
            idempotency_key TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            payload TEXT NOT NULL,
            result TEXT,
            error TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key);
        CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
        """
    )


@migration(3, "add_job_leases_and_fencing")
def migrate_003_job_leases(conn: sqlite3.Connection):
    columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
    additions = {
        "lease_owner": "TEXT",
        "lease_expires_at": "TEXT",
        "fence_token": "INTEGER NOT NULL DEFAULT 0",
        "attempts": "INTEGER NOT NULL DEFAULT 0",
        "max_attempts": "INTEGER NOT NULL DEFAULT 3",
    }
    for name, declaration in additions.items():
        if name not in columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {declaration}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_lease ON jobs(status, lease_expires_at)")


@migration(4, "add_job_checkpoints_and_artifact_lifecycle")
def migrate_004_checkpoints_and_lifecycle(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS job_checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            step INTEGER NOT NULL DEFAULT 0,
            total_steps INTEGER NOT NULL DEFAULT 1,
            progress_percent REAL NOT NULL DEFAULT 0.0,
            state_data TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_checkpoints_job ON job_checkpoints(job_id, created_at);

        CREATE TABLE IF NOT EXISTS artifact_lifecycle (
            artifact_uri TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            sha256 TEXT NOT NULL,
            exported_at TEXT,
            created_at TEXT NOT NULL,
            expires_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_artifact_lifecycle_status ON artifact_lifecycle(status, expires_at);
        """
    )


@migration(5, "add_agent_insights")
def migrate_005_insights(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agent_insights (
            insight_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            summary TEXT NOT NULL,
            details TEXT,
            model_id TEXT,
            dataset_id TEXT,
            tags TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_insights_tenant ON agent_insights(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_insights_model ON agent_insights(tenant_id, model_id);
        CREATE INDEX IF NOT EXISTS idx_insights_dataset ON agent_insights(tenant_id, dataset_id);
        CREATE INDEX IF NOT EXISTS idx_insights_category ON agent_insights(tenant_id, category);
        CREATE INDEX IF NOT EXISTS idx_insights_created ON agent_insights(created_at DESC);
        """
    )


@migration(6, "add_tenant_id_to_core_resources")
def migrate_006_tenant_scoping(conn: sqlite3.Connection):
    for tbl in ("datasets", "models", "scenarios", "clv_models"):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({tbl})").fetchall()}
        if "tenant_id" not in cols:
            conn.execute(f"ALTER TABLE {tbl} ADD COLUMN tenant_id TEXT")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_tenant ON {tbl}(tenant_id)")


@migration(7, "add_organization_mapping_profiles")
def migrate_007_mapping_profiles(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS organization_mapping_profiles (
            profile_id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL,
            profile_name TEXT NOT NULL,
            mappings TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mapping_profiles_org ON organization_mapping_profiles(organization_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mapping_profiles_org_name ON organization_mapping_profiles(organization_id, profile_name);
        """
    )


@migration(8, "add_experiments_table")
def migrate_008_experiments(conn: sqlite3.Connection):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS experiments (
            experiment_id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            channel TEXT NOT NULL,
            archived INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_experiments_tenant ON experiments(tenant_id);
        CREATE INDEX IF NOT EXISTS idx_experiments_channel ON experiments(channel);
        """
    )


class MigrationRunner:
    """Applies ordered migrations and tracks schema version."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_migrations_table()

    def _ensure_migrations_table(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            );
            """
        )
        self.conn.commit()

    def current_version(self) -> int:
        row = self.conn.execute(
            "SELECT MAX(version) as max_v FROM schema_migrations"
        ).fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return 0

    def apply_pending(self) -> list[int]:
        current = self.current_version()
        applied = []
        for version, name, fn in MIGRATIONS:
            if version > current:
                fn(self.conn)
                now = datetime.now(UTC).isoformat()
                self.conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, now),
                )
                self.conn.commit()
                applied.append(version)
        return applied
