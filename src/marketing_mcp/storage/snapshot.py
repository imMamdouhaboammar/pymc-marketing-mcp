"""Durable snapshots of the SQLite metadata database.

SQLite cannot live on an object-store mount (no POSIX locks), and container-local disk
disappears with the instance. For a single-instance deployment the database therefore
runs on local disk and is copied to a durable path: restored at startup when the local
file is missing, refreshed on an interval, and written once more at shutdown.

Snapshots are only safe with one writer. Run exactly one instance when this is enabled.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import threading
from pathlib import Path

from marketing_mcp.errors import DomainError

logger = logging.getLogger(__name__)


def restore_if_missing(database: Path, snapshot: Path) -> bool:
    """Copy the snapshot into place when the local database does not exist yet."""
    if database.exists() or not snapshot.is_file():
        return False
    _check_integrity(snapshot)
    database.parent.mkdir(parents=True, exist_ok=True)
    staging = database.with_name(f".{database.name}.restore")
    shutil.copyfile(snapshot, staging)
    os.replace(staging, database)
    logger.info("Restored metadata database from snapshot %s", snapshot)
    return True


def write_snapshot(database: Path, snapshot: Path) -> None:
    """Write a consistent copy of the live database, replacing the previous snapshot."""
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    staging = snapshot.with_name(f".{snapshot.name}.tmp")
    staging.unlink(missing_ok=True)
    source = sqlite3.connect(database)
    try:
        target = sqlite3.connect(staging)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
    _check_integrity(staging)
    os.replace(staging, snapshot)


def _check_integrity(path: Path) -> None:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    finally:
        connection.close()
    if result is None or result[0] != "ok":
        raise DomainError(
            "DEPENDENCY_UNAVAILABLE",
            "Metadata snapshot failed its integrity check",
            evidence={"path": str(path)},
            next_action="Restore an earlier snapshot version from the storage bucket",
        )


def _fingerprint(database: Path) -> tuple[tuple[int, int], ...]:
    stats = []
    for path in (database, database.with_name(f"{database.name}-wal")):
        try:
            stat = path.stat()
        except FileNotFoundError:
            stats.append((0, 0))
        else:
            stats.append((stat.st_mtime_ns, stat.st_size))
    return tuple(stats)


class MetadataSnapshotter:
    """Background thread that keeps the durable snapshot current."""

    def __init__(self, database: Path, snapshot: Path, interval_seconds: float = 300.0):
        self.database = database
        self.snapshot = snapshot
        self.interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_fingerprint: tuple[tuple[int, int], ...] | None = None

    def snapshot_now(self) -> bool:
        """Write a snapshot if the database changed since the last one."""
        if not self.database.exists():
            return False
        fingerprint = _fingerprint(self.database)
        if fingerprint == self._last_fingerprint:
            return False
        write_snapshot(self.database, self.snapshot)
        self._last_fingerprint = fingerprint
        return True

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            try:
                self.snapshot_now()
            except Exception:
                logger.exception("Metadata snapshot failed; will retry next interval")

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="metadata-snapshot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the loop and write a final snapshot."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds)
        try:
            self.snapshot_now()
        except Exception:
            logger.exception("Final metadata snapshot failed")


__all__ = ["MetadataSnapshotter", "restore_if_missing", "write_snapshot"]
