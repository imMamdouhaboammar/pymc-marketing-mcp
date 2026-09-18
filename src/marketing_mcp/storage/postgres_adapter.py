"""PostgreSQL storage adapter implementing MetadataRepository and JobRepository.

Designed for multi-tenant, multi-worker production deployments using DB-API 2.0
and SELECT ... FOR UPDATE SKIP LOCKED for concurrent worker task claiming.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord, JobStatus


class PostgresStorageAdapter:
    """PostgreSQL production persistence adapter with tenant isolation and row-level locking."""

    def __init__(self, connection_or_pool: Any):
        self.pool = connection_or_pool

    def _get_conn(self):
        if hasattr(self.pool, "cursor"):
            return self.pool
        if hasattr(self.pool, "getconn"):
            return self.pool.getconn()
        if hasattr(self.pool, "connection"):
            return self.pool.connection()
        return self.pool

    # --- MetadataRepository implementation ---

    def put_dataset(self, payload: dict[str, Any], tenant_id: str | None = None) -> None:
        t_id = tenant_id if tenant_id is not None else payload.get("tenant_id")
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO datasets (dataset_id, tenant_id, payload)
                VALUES (%s, %s, %s)
                ON CONFLICT (dataset_id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    payload = EXCLUDED.payload
                """,
                (payload["dataset_id"], t_id, json.dumps(payload)),
            )
        conn.commit()

    def get_dataset(self, dataset_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            if tenant_id is not None:
                cur.execute(
                    "SELECT payload FROM datasets WHERE dataset_id = %s AND (tenant_id = %s OR tenant_id IS NULL)",
                    (dataset_id, tenant_id),
                )
            else:
                cur.execute("SELECT payload FROM datasets WHERE dataset_id = %s", (dataset_id,))
            row = cur.fetchone()
            if not row:
                raise DomainError("DATASET_NOT_FOUND", f"Dataset '{dataset_id}' was not found")
            return json.loads(row[0]) if isinstance(row[0], str) else row[0]

    def list_datasets(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            if tenant_id is not None:
                cur.execute(
                    "SELECT payload FROM datasets WHERE tenant_id = %s OR tenant_id IS NULL ORDER BY created_at DESC",
                    (tenant_id,),
                )
            else:
                cur.execute("SELECT payload FROM datasets ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [json.loads(r[0]) if isinstance(r[0], str) else r[0] for r in rows]

    def put_model(self, payload: dict[str, Any], tenant_id: str | None = None) -> None:
        t_id = tenant_id if tenant_id is not None else payload.get("tenant_id")
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO models (model_id, tenant_id, payload)
                VALUES (%s, %s, %s)
                ON CONFLICT (model_id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    payload = EXCLUDED.payload
                """,
                (payload["model_id"], t_id, json.dumps(payload)),
            )
        conn.commit()

    def get_model(self, model_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            if tenant_id is not None:
                cur.execute(
                    "SELECT payload FROM models WHERE model_id = %s AND (tenant_id = %s OR tenant_id IS NULL)",
                    (model_id, tenant_id),
                )
            else:
                cur.execute("SELECT payload FROM models WHERE model_id = %s", (model_id,))
            row = cur.fetchone()
            if not row:
                raise DomainError("MODEL_NOT_FOUND", f"Model '{model_id}' was not found")
            return json.loads(row[0]) if isinstance(row[0], str) else row[0]

    def list_models(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        with conn.cursor() as cur:
            if tenant_id is not None:
                cur.execute(
                    "SELECT payload FROM models WHERE tenant_id = %s OR tenant_id IS NULL ORDER BY created_at DESC",
                    (tenant_id,),
                )
            else:
                cur.execute("SELECT payload FROM models ORDER BY created_at DESC")
            rows = cur.fetchall()
            return [json.loads(r[0]) if isinstance(r[0], str) else r[0] for r in rows]

    # --- JobRepository implementation with SKIP LOCKED ---

    def create_job(self, record: JobRecord) -> JobRecord:
        now = datetime.now(UTC).isoformat()
        record.created_at = now
        record.updated_at = now
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (
                    job_id, job_type, status, owner, tenant_id, idempotency_key,
                    created_at, updated_at, payload, result, error, lease_owner,
                    lease_expires_at, fence_token, attempts, max_attempts
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        conn.commit()
        return record

    def claim_next_job(
        self,
        tenant_id: str | None = None,
        *,
        worker_id: str = "worker",
        lease_seconds: int = 60,
    ) -> JobRecord | None:
        """Concurrently claim the next available job using SELECT ... FOR UPDATE SKIP LOCKED."""
        now = datetime.now(UTC)
        expires_at = (now + datetime.timedelta(seconds=lease_seconds)).isoformat()
        now_str = now.isoformat()

        conn = self._get_conn()
        with conn.cursor() as cur:
            query = """
                SELECT job_id, fence_token, attempts
                FROM jobs
                WHERE status = 'queued'
            """
            params: list[Any] = []
            if tenant_id is not None:
                query += " AND (tenant_id = %s OR tenant_id IS NULL)"
                params.append(tenant_id)
            query += " ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1"

            cur.execute(query, params)
            row = cur.fetchone()
            if not row:
                return None

            job_id, fence_token, _attempts = row[0], row[1], row[2]
            new_fence = fence_token + 1

            cur.execute(
                """
                UPDATE jobs
                SET status = 'running',
                    lease_owner = %s,
                    lease_expires_at = %s,
                    fence_token = %s,
                    attempts = attempts + 1,
                    updated_at = %s
                WHERE job_id = %s AND fence_token = %s
                RETURNING *
                """,
                (worker_id, expires_at, new_fence, now_str, job_id, fence_token),
            )
            updated_row = cur.fetchone()
            if not updated_row:
                return None

        conn.commit()
        return self.get_job(job_id, tenant_id=tenant_id)

    def get_job(self, job_id: str, tenant_id: str | None = None) -> JobRecord:
        conn = self._get_conn()
        with conn.cursor() as cur:
            if tenant_id is not None:
                cur.execute(
                    "SELECT * FROM jobs WHERE job_id = %s AND (tenant_id = %s OR tenant_id IS NULL)",
                    (job_id, tenant_id),
                )
            else:
                cur.execute("SELECT * FROM jobs WHERE job_id = %s", (job_id,))
            row = cur.fetchone()
            if not row:
                raise DomainError("JOB_NOT_FOUND", f"Job '{job_id}' was not found")
            cols = [desc[0] for desc in cur.description]
            d = dict(zip(cols, row))
            return JobRecord(
                job_id=d["job_id"],
                job_type=d["job_type"],
                status=JobStatus(d["status"]),
                owner=d["owner"],
                tenant_id=d.get("tenant_id"),
                idempotency_key=d.get("idempotency_key"),
                created_at=d["created_at"],
                updated_at=d["updated_at"],
                payload=json.loads(d["payload"]) if isinstance(d["payload"], str) else d["payload"],
                result=json.loads(d["result"]) if isinstance(d.get("result"), str) else d.get("result"),
                error=json.loads(d["error"]) if isinstance(d.get("error"), str) else d.get("error"),
                lease_owner=d.get("lease_owner"),
                lease_expires_at=d.get("lease_expires_at"),
                fence_token=d.get("fence_token", 0),
                attempts=d.get("attempts", 0),
                max_attempts=d.get("max_attempts", 3),
            )
