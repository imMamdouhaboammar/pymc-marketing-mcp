"""SQLite implementation of CredentialRepository."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path

from marketing_mcp.credentials.models import CredentialAuditRecord, CredentialRecord
from marketing_mcp.credentials.repository import CredentialRepository


class SQLiteCredentialRepository(CredentialRepository):
    """Thread-safe SQLite storage for credentials and audit events."""

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            self._local.conn = conn
        return self._local.conn

    def close(self) -> None:
        connection = getattr(self._local, "conn", None)
        if connection is not None:
            connection.close()
            self._local.conn = None

    def _init_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credentials (
                    credential_id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    owner_subject TEXT NOT NULL,
                    name TEXT NOT NULL,
                    prefix TEXT NOT NULL,
                    verifier TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    scopes TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    revoked_at TEXT,
                    last_used_at TEXT
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_credentials_prefix ON credentials(prefix, status);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_credentials_tenant_owner ON credentials(tenant_id, owner_subject);"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS credential_audit_events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    actor_subject TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    credential_id TEXT,
                    prefix TEXT,
                    details TEXT
                );
                """
            )

    def _row_to_record(self, row: sqlite3.Row) -> CredentialRecord:
        scopes_raw = row["scopes"]
        try:
            scopes = frozenset(json.loads(scopes_raw))
        except (json.JSONDecodeError, TypeError):
            scopes = frozenset(s.strip() for s in scopes_raw.split(",") if s.strip())

        return CredentialRecord(
            credential_id=row["credential_id"],
            tenant_id=row["tenant_id"],
            owner_subject=row["owner_subject"],
            name=row["name"],
            prefix=row["prefix"],
            verifier=row["verifier"],
            salt=row["salt"],
            scopes=scopes,
            status=row["status"],
            created_at=row["created_at"],
            revoked_at=row["revoked_at"],
            last_used_at=row["last_used_at"],
        )

    def create(self, record: CredentialRecord) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO credentials (
                    credential_id, tenant_id, owner_subject, name, prefix,
                    verifier, salt, scopes, status, created_at, revoked_at, last_used_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.credential_id,
                    record.tenant_id,
                    record.owner_subject,
                    record.name,
                    record.prefix,
                    record.verifier,
                    record.salt,
                    json.dumps(sorted(record.scopes)),
                    record.status,
                    record.created_at,
                    record.revoked_at,
                    record.last_used_at,
                ),
            )

    def get_by_id(self, credential_id: str) -> CredentialRecord | None:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM credentials WHERE credential_id = ?",
            (credential_id,),
        )
        row = cursor.fetchone()
        return self._row_to_record(row) if row else None

    def find_active_by_prefix(self, prefix: str) -> Sequence[CredentialRecord]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM credentials WHERE prefix = ? AND status = 'active'",
            (prefix,),
        )
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def list_by_owner(self, tenant_id: str, owner_subject: str) -> Sequence[CredentialRecord]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM credentials WHERE tenant_id = ? AND owner_subject = ? ORDER BY created_at DESC",
            (tenant_id, owner_subject),
        )
        return [self._row_to_record(r) for r in cursor.fetchall()]

    def update_status(self, credential_id: str, status: str, revoked_at: str | None = None) -> CredentialRecord:
        conn = self._get_conn()
        with conn:
            conn.execute(
                "UPDATE credentials SET status = ?, revoked_at = ? WHERE credential_id = ?",
                (status, revoked_at, credential_id),
            )
        rec = self.get_by_id(credential_id)
        if rec is None:
            raise KeyError(f"Credential {credential_id} not found")
        return rec

    def record_usage(self, credential_id: str, last_used_at: str) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute(
                "UPDATE credentials SET last_used_at = ? WHERE credential_id = ?",
                (last_used_at, credential_id),
            )

    def append_audit_event(self, event: CredentialAuditRecord) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute(
                """
                INSERT INTO credential_audit_events (
                    event_id, event_type, tenant_id, actor_subject, timestamp,
                    credential_id, prefix, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.event_type,
                    event.tenant_id,
                    event.actor_subject,
                    event.timestamp,
                    event.credential_id,
                    event.prefix,
                    json.dumps(event.details),
                ),
            )

    def list_audit_events(self, tenant_id: str, limit: int = 100) -> Sequence[CredentialAuditRecord]:
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM credential_audit_events WHERE tenant_id = ? ORDER BY timestamp DESC LIMIT ?",
            (tenant_id, limit),
        )
        events = []
        for r in cursor.fetchall():
            details = {}
            if r["details"]:
                try:
                    details = json.loads(r["details"])
                except (json.JSONDecodeError, TypeError):
                    details = {}
            events.append(
                CredentialAuditRecord(
                    event_id=r["event_id"],
                    event_type=r["event_type"],
                    tenant_id=r["tenant_id"],
                    actor_subject=r["actor_subject"],
                    timestamp=r["timestamp"],
                    credential_id=r["credential_id"],
                    prefix=r["prefix"],
                    details=details,
                )
            )
        return events


__all__ = ["SQLiteCredentialRepository"]
