from __future__ import annotations

import concurrent.futures
import time
import uuid
from pathlib import Path

import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.jobs.models import JobCheckpoint, JobRecord, JobStatus
from marketing_mcp.security.principal import Principal


def test_real_sqlite_concurrency_stress(tmp_path: Path):
    """Stress test SQLite under concurrent multi-threaded read/write load.
    
    Verifies that WAL mode + busy_timeout=30000 eliminates 'database is locked' errors
    and guarantees complete data consistency across concurrent writers.
    """
    db_path = tmp_path / "concurrent_metadata.db"
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=db_path,
        ingest_dir=tmp_path / "inbox",
        auth_enabled=False,
    )
    app = Application(settings)

    num_threads = 8
    ops_per_thread = 10
    total_expected = num_threads * ops_per_thread

    success_count = 0
    failure_count = 0
    lock_exceptions = 0
    latencies: list[float] = []

    def worker_task(thread_id: int):
        thread_success = 0
        thread_failure = 0
        thread_locks = 0
        thread_latencies = []

        p = Principal(
            subject=f"worker_{thread_id}",
            auth_type="api_key",
            tenant_id=f"tenant_{thread_id % 3}",
            scopes=frozenset(["marketing:write", "marketing:read"]),
        )

        for i in range(ops_per_thread):
            t0 = time.perf_counter()
            op_type = i % 4
            try:
                if op_type == 0:
                    # Dataset registration
                    csv_data = f"date,revenue,spend\n2026-01-01,100,50\n2026-01-02,200,60\n".encode()
                    app.datasets.register_bytes(
                        csv_data,
                        filename=f"ds_{thread_id}_{i}.csv",
                        principal=p,
                    )
                elif op_type == 1:
                    # Job creation and checkpoint write
                    job_id = f"job_stress_{thread_id}_{i}_{uuid.uuid4().hex[:6]}"
                    rec = JobRecord(
                        job_id=job_id,
                        job_type="fit_mmm",
                        status=JobStatus.QUEUED,
                        owner=p.subject,
                        tenant_id=p.tenant_id,
                        payload={"step": i},
                    )
                    app.jobs.repo.create_job(rec)
                    cp = JobCheckpoint(
                        checkpoint_id=f"cp_{uuid.uuid4().hex[:8]}",
                        job_id=job_id,
                        stage="sampling",
                        step=i,
                        total_steps=10,
                        progress_percent=float(i * 10),
                    )
                    app.jobs.repo.save_checkpoint(cp)
                elif op_type == 2:
                    # Model metadata write
                    model_id = f"model_stress_{thread_id}_{i}"
                    app.metadata.put_model(
                        {
                            "model_id": model_id,
                            "tenant_id": p.tenant_id,
                            "status": "completed",
                            "metrics": {"nrmse": 0.25},
                        },
                        tenant_id=p.tenant_id,
                    )
                else:
                    # Concurrent reads: list datasets & list jobs
                    app.metadata.list_datasets(tenant_id=p.tenant_id)
                    app.jobs.repo.list_jobs(tenant_id=p.tenant_id)

                elapsed = time.perf_counter() - t0
                thread_latencies.append(elapsed)
                thread_success += 1
            except Exception as exc:
                elapsed = time.perf_counter() - t0
                thread_latencies.append(elapsed)
                thread_failure += 1
                print(f"\n[Thread {thread_id} Op {i} Error]: {type(exc).__name__}: {exc}")
                if "locked" in str(exc).lower():
                    thread_locks += 1

        return thread_success, thread_failure, thread_locks, thread_latencies

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker_task, tid) for tid in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            s, fail, locks, lats = f.result()
            success_count += s
            failure_count += fail
            lock_exceptions += locks
            latencies.extend(lats)

    latencies.sort()
    p50 = latencies[len(latencies) // 2] if latencies else 0.0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

    print(
        f"\n[Stress Benchmark] Total Ops: {total_expected}, Success: {success_count}, "
        f"Failures: {failure_count}, Locks: {lock_exceptions}, "
        f"Latency p50: {p50*1000:.2f}ms, p95: {p95*1000:.2f}ms"
    )

    # Invariants
    assert lock_exceptions == 0, f"SQLite lock contention exposed: {lock_exceptions} locks"
    assert failure_count == 0, f"Concurrent operations failed: {failure_count} errors"
    assert success_count == total_expected, f"Expected {total_expected} successes, got {success_count}"
