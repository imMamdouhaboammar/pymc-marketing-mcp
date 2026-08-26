"""Integration tests for schema-versioned SQLite migrations (Wave 5 Task 2)."""

from __future__ import annotations

from marketing_mcp.storage.metadata import SQLiteMetadataStore
from marketing_mcp.storage.migrations import MigrationRunner


class TestSQLiteMigrations:
    def test_migrations_applied_on_initialization(self, tmp_path):
        db_path = tmp_path / "metadata.db"
        store = SQLiteMetadataStore(db_path)
        runner = MigrationRunner(store.conn)
        assert runner.current_version() >= 2

        # Verify tables and indices exist
        cursor = store.conn.cursor()
        tables = {row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"datasets", "models", "scenarios", "clv_models", "jobs", "schema_migrations"}.issubset(tables)
        store.close()

    def test_migrations_idempotent_on_reopen(self, tmp_path):
        db_path = tmp_path / "metadata.db"
        store1 = SQLiteMetadataStore(db_path)
        v1 = MigrationRunner(store1.conn).current_version()
        store1.close()

        store2 = SQLiteMetadataStore(db_path)
        v2 = MigrationRunner(store2.conn).current_version()
        assert v1 == v2
        store2.close()
