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
