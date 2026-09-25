"""Snapshot/restore of the SQLite metadata database across instance replacement."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.storage.snapshot import MetadataSnapshotter, restore_if_missing, write_snapshot


def _settings(root: Path, local: Path) -> Settings:
    return Settings(
        data_dir=root / "data",
        artifact_dir=root / "artifacts",
        ingest_dir=root / "inbox",
        metadata_db=local / "metadata.db",
    )


def test_state_survives_loss_of_local_disk(tmp_path: Path):
    durable = tmp_path / "durable"
    snapshot = durable / "state" / "metadata.db"
    first_disk = tmp_path / "instance-1"

    app = Application(_settings(durable, first_disk))
    issued = app.credentials.issue(
        tenant_id="tenant_a", owner_subject="alice", name="ci", scopes=["marketing:read"]
    )
    snapshotter = MetadataSnapshotter(app.settings.metadata_db, snapshot)
    assert snapshotter.snapshot_now() is True
    app.persistence.close()

    # A replacement instance starts with an empty local disk.
    second_disk = tmp_path / "instance-2"
    settings = _settings(durable, second_disk)
    assert restore_if_missing(settings.metadata_db, snapshot) is True
    restored = Application(settings)

    records = restored.credentials.list_for_owner(tenant_id="tenant_a", owner_subject="alice")
    assert [r.credential_id for r in records] == [issued.record.credential_id]
    restored.persistence.close()


def test_restore_never_overwrites_an_existing_database(tmp_path: Path):
    database = tmp_path / "metadata.db"
    snapshot = tmp_path / "snapshot.db"
    sqlite3.connect(database).execute("CREATE TABLE live (x)").connection.commit()
    sqlite3.connect(snapshot).execute("CREATE TABLE stale (x)").connection.commit()

    assert restore_if_missing(database, snapshot) is False
    tables = {
        row[0]
        for row in sqlite3.connect(database).execute("SELECT name FROM sqlite_master")
    }
    assert tables == {"live"}


def test_corrupt_snapshot_refuses_restore(tmp_path: Path):
    snapshot = tmp_path / "snapshot.db"
    snapshot.write_bytes(b"SQLite format 3\x00" + b"\xff" * 4096)

    with pytest.raises((DomainError, sqlite3.DatabaseError)):
        restore_if_missing(tmp_path / "metadata.db", snapshot)
    assert not (tmp_path / "metadata.db").exists()


def test_unchanged_database_is_not_rewritten(tmp_path: Path):
    database = tmp_path / "metadata.db"
    sqlite3.connect(database).execute("CREATE TABLE t (x)").connection.commit()
    snapshotter = MetadataSnapshotter(database, tmp_path / "out" / "snapshot.db")

    assert snapshotter.snapshot_now() is True
    assert snapshotter.snapshot_now() is False


def test_snapshot_replaces_previous_copy_atomically(tmp_path: Path):
    database = tmp_path / "metadata.db"
    snapshot = tmp_path / "snapshot.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE t (x)")
    connection.commit()
    write_snapshot(database, snapshot)
    connection.execute("INSERT INTO t VALUES (1)")
    connection.commit()

    write_snapshot(database, snapshot)

    assert sqlite3.connect(snapshot).execute("SELECT COUNT(*) FROM t").fetchone() == (1,)
    assert not list(tmp_path.glob(".snapshot.db.tmp"))


def test_snapshot_path_must_differ_from_database(tmp_path: Path):
    with pytest.raises(DomainError):
        Settings(metadata_db=tmp_path / "m.db", metadata_snapshot=tmp_path / "m.db")


def test_snapshot_of_wal_database_is_a_single_file(tmp_path: Path):
    database = tmp_path / "live" / "metadata.db"
    database.parent.mkdir()
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE t (x)")
    connection.execute("INSERT INTO t VALUES (1)")
    connection.commit()
    out = tmp_path / "durable"

    write_snapshot(database, out / "metadata.db")

    assert sorted(p.name for p in out.iterdir()) == ["metadata.db"]
    snapshot = sqlite3.connect(out / "metadata.db")
    assert snapshot.execute("PRAGMA journal_mode").fetchone() == ("delete",)
    assert snapshot.execute("SELECT x FROM t").fetchall() == [(1,)]
