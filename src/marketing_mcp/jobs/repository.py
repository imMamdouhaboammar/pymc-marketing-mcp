"""Job persistence repository for SQLite and in-memory execution."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
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
    def claim_next_job(
        self,
        tenant_id: str | None = None,
        *,
        worker_id: str = "worker",
        lease_seconds: int = 60,
    ) -> JobRecord | None: ...
    def renew_lease(
        self, job_id: str, *, worker_id: str, fence_token: int, lease_seconds: int = 60
    ) -> bool: ...
    def finish_claim(
        self,
        job_id: str,
        *,
        worker_id: str,
        fence_token: int,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> JobRecord: ...
    def request_cancellation(self, job_id: str) -> JobRecord: ...
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
                created_at, updated_at, payload, result, error, lease_owner,
                lease_expires_at, fence_token, attempts, max_attempts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                record.lease_owner,
                record.lease_expires_at,
                record.fence_token,
                record.attempts,
                record.max_attempts,
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

    def claim_next_job(
        self,
        tenant_id: str | None = None,
        *,
        worker_id: str = "worker",
        lease_seconds: int = 60,
    ) -> JobRecord | None:
        """Atomically claim the oldest eligible queued job with a fenced lease."""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            query = "SELECT job_id FROM jobs WHERE status = ? AND attempts < max_attempts"
            params: list[Any] = [JobStatus.QUEUED.value]
            if tenant_id is not None:
                query += " AND tenant_id = ?"
                params.append(tenant_id)
            query += " ORDER BY created_at ASC, job_id ASC LIMIT 1"
            row = self.conn.execute(query, params).fetchone()
            if row is None:
                self.conn.commit()
                return None

            now = datetime.now(UTC)
            cursor = self.conn.execute(
                """
                UPDATE jobs
                SET status = ?, updated_at = ?, lease_owner = ?, lease_expires_at = ?,
                    fence_token = fence_token + 1, attempts = attempts + 1
                WHERE job_id = ? AND status = ? AND attempts < max_attempts
                """,
                (
                    JobStatus.RUNNING.value,
                    now.isoformat(),
                    worker_id,
                    (now + timedelta(seconds=lease_seconds)).isoformat(),
                    row["job_id"],
                    JobStatus.QUEUED.value,
                ),
            )
            self.conn.commit()
            if cursor.rowcount != 1:  # pragma: no cover - BEGIN IMMEDIATE serializes SQLite writers
                return None
            return self.get_job(row["job_id"])
        except Exception:
            self.conn.rollback()
            raise

    def renew_lease(
        self, job_id: str, *, worker_id: str, fence_token: int, lease_seconds: int = 60
    ) -> bool:
        """Extend only the currently owned running attempt."""
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        now = datetime.now(UTC)
        cursor = self.conn.execute(
            """
            UPDATE jobs
            SET lease_expires_at = ?, updated_at = ?
            WHERE job_id = ? AND status = 'running' AND lease_owner = ? AND fence_token = ?
            """,
            (
                (now + timedelta(seconds=lease_seconds)).isoformat(),
                now.isoformat(),
                job_id,
                worker_id,
                fence_token,
            ),
        )
        self.conn.commit()
        return cursor.rowcount == 1

    def finish_claim(
        self,
        job_id: str,
        *,
        worker_id: str,
        fence_token: int,
        status: JobStatus,
        result: dict[str, Any] | None = None,
        error: dict[str, Any] | None = None,
    ) -> JobRecord:
        """Commit one terminal result only when the lease and fence still match."""
        if status not in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            raise ValueError("a claimed job can finish only in a terminal state")
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise DomainError("JOB_NOT_FOUND", f"Job '{job_id}' was not found")
            current = self._row_to_record(row)
            if current.lease_owner != worker_id or current.fence_token != fence_token:
                raise DomainError("STALE_JOB_CLAIM", "stale job claim cannot publish a result")
            if current.status is JobStatus.CANCELLING and status is not JobStatus.CANCELLED:
                raise DomainError("JOB_CANCELLED", "job cancellation prevents result publication")
            if current.status not in {JobStatus.RUNNING, JobStatus.CANCELLING}:
                raise DomainError("STALE_JOB_CLAIM", "stale job claim cannot publish a result")
            validate_transition(current.status, status)
            now = datetime.now(UTC).isoformat()
            cursor = self.conn.execute(
                """
                UPDATE jobs
                SET status = ?, result = ?, error = ?, updated_at = ?,
                    lease_owner = NULL, lease_expires_at = NULL
                WHERE job_id = ? AND status = ? AND lease_owner = ? AND fence_token = ?
                """,
                (
                    status.value,
                    json.dumps(result) if result is not None else None,
                    json.dumps(error) if error is not None else None,
                    now,
                    job_id,
                    current.status.value,
                    worker_id,
                    fence_token,
                ),
            )
            if cursor.rowcount != 1:
                raise DomainError("STALE_JOB_CLAIM", "stale job claim cannot publish a result")
            self.conn.commit()
            return self.get_job(job_id)
        except Exception:
            self.conn.rollback()
            raise

    def request_cancellation(self, job_id: str) -> JobRecord:
        """Make queued cancellation terminal and running cancellation worker-observable."""
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            row = self.conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                raise DomainError("JOB_NOT_FOUND", f"Job '{job_id}' was not found")
            current = self._row_to_record(row)
            if current.status is JobStatus.QUEUED:
                target = JobStatus.CANCELLED
            elif current.status is JobStatus.RUNNING:
                target = JobStatus.CANCELLING
            else:
                self.conn.commit()
                return current
            now = datetime.now(UTC).isoformat()
            self.conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ? AND status = ?",
                (target.value, now, job_id, current.status.value),
            )
            self.conn.commit()
            return self.get_job(job_id)
        except Exception:
            self.conn.rollback()
            raise

    def recover_stale_running_jobs(self) -> int:
        """Recover only attempts whose explicit worker lease has expired."""
        now = datetime.now(UTC).isoformat()
        retry_error = json.dumps(
            {"code": "WORKER_LEASE_EXPIRED", "message": "Worker lease expired; job was requeued."}
        )
        failed_error = json.dumps(
            {"code": "WORKER_ATTEMPTS_EXHAUSTED", "message": "Worker retries were exhausted."}
        )
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            requeued = self.conn.execute(
                """
                UPDATE jobs
                SET status = 'queued', error = ?, updated_at = ?,
                    lease_owner = NULL, lease_expires_at = NULL
                WHERE status = 'running' AND lease_expires_at IS NOT NULL
                  AND lease_expires_at <= ? AND attempts < max_attempts
                """,
                (retry_error, now, now),
            ).rowcount
            failed = self.conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', error = ?, updated_at = ?,
                    lease_owner = NULL, lease_expires_at = NULL
                WHERE status = 'running' AND lease_expires_at IS NOT NULL
                  AND lease_expires_at <= ? AND attempts >= max_attempts
                """,
                (failed_error, now, now),
            ).rowcount
            cancelled = self.conn.execute(
                """
                UPDATE jobs
                SET status = 'cancelled', updated_at = ?,
                    lease_owner = NULL, lease_expires_at = NULL
                WHERE status = 'cancelling' AND lease_expires_at IS NOT NULL
                  AND lease_expires_at <= ?
                """,
                (now, now),
            ).rowcount
            self.conn.commit()
            return requeued + failed + cancelled
        except Exception:
            self.conn.rollback()
            raise

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
            lease_owner=row["lease_owner"],
            lease_expires_at=row["lease_expires_at"],
            fence_token=row["fence_token"],
            attempts=row["attempts"],
            max_attempts=row["max_attempts"],
        )
