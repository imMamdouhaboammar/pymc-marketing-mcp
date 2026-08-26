"""Job persistence repository for SQLite and in-memory execution."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Protocol

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.state import validate_transition


class JobRepository(Protocol):
    """Abstract job repository protocol."""

    def create_job(self, record: JobRecord) -> JobRecord: ...
    def get_job(self, job_id: str) -> JobRecord: ...
    def update_job(
        self,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> JobRecord: ...
    def list_jobs(
        self,
        tenant_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[JobRecord]: ...
    def find_by_idempotency_key(self, key: str, tenant_id: str | None = None) -> JobRecord | None: ...
    def recover_stale_running_jobs(self) -> int: ...


class SQLiteJobRepository:
    """SQLite implementation of JobRepository."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_job(self, record: JobRecord) -> JobRecord:
        now = datetime.now(UTC).isoformat()
        record.created_at = now
        record.updated_at = now
        self.conn.execute(
            """
            INSERT INTO jobs (
                job_id, job_type, status, owner, tenant_id, idempotency_key,
                created_at, updated_at, payload, result, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.job_id,
                record.job_type,
                record.status.value,
                record.owner,
                record.tenant_id,
                record.idempotency_key,
                record.created_at,
                record.updated_at,
                json.dumps(record.payload),
                json.dumps(record.result) if record.result else None,
                json.dumps(record.error) if record.error else None,
            ),
        )
        self.conn.commit()
        return record

    def get_job(self, job_id: str) -> JobRecord:
        row = self.conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if not row:
            raise DomainError("JOB_NOT_FOUND", f"Job '{job_id}' was not found")
        return self._row_to_record(row)

    def update_job(
        self,
        job_id: str,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> JobRecord:
        current = self.get_job(job_id)
        validate_transition(current.status, status)

        now = datetime.now(UTC).isoformat()
        res_json = json.dumps(result) if result is not None else (json.dumps(current.result) if current.result else None)
        err_json = json.dumps(error) if error is not None else (json.dumps(current.error) if current.error else None)

        self.conn.execute(
            """
            UPDATE jobs
            SET status = ?, result = ?, error = ?, updated_at = ?
            WHERE job_id = ?
            """,
            (status.value, res_json, err_json, now, job_id),
        )
        self.conn.commit()
        return self.get_job(job_id)

    def list_jobs(
        self,
        tenant_id: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[Any] = []
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        if status is not None:
            query += " AND status = ?"
            params.append(status.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def find_by_idempotency_key(self, key: str, tenant_id: str | None = None) -> JobRecord | None:
        query = "SELECT * FROM jobs WHERE idempotency_key = ?"
        params: list[Any] = [key]
        if tenant_id is not None:
            query += " AND tenant_id = ?"
            params.append(tenant_id)
        row = self.conn.execute(query, params).fetchone()
        if not row:
            return None
        return self._row_to_record(row)

    def recover_stale_running_jobs(self) -> int:
        """Mark uncompleted running jobs as failed on process startup (crash recovery)."""
        now = datetime.now(UTC).isoformat()
        err_payload = json.dumps(
            {
                "code": "WORKER_CRASHED",
                "message": "Process restarted while job was executing. Job recovered as failed.",
            }
        )
        cursor = self.conn.execute(
            """
            UPDATE jobs
            SET status = 'failed', error = ?, updated_at = ?
            WHERE status IN ('running', 'cancelling')
            """,
            (err_payload, now),
        )
        self.conn.commit()
        return cursor.rowcount

    def _row_to_record(self, row) -> JobRecord:
        return JobRecord(
            job_id=row["job_id"],
            job_type=row["job_type"],
            status=JobStatus(row["status"]),
            owner=row["owner"],
            tenant_id=row["tenant_id"],
            idempotency_key=row["idempotency_key"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            payload=json.loads(row["payload"]) if row["payload"] else {},
            result=json.loads(row["result"]) if row["result"] else None,
            error=json.loads(row["error"]) if row["error"] else None,
        )
