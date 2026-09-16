"""Executable characterization tests for job lifecycle, leases, fencing, and idempotency (UP-005)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.jobs.state import can_transition, validate_transition
from marketing_mcp.storage.migrations import MigrationRunner

BASELINES_DIR = Path(__file__).resolve().parent.parent.parent / "migration" / "baselines"


@pytest.fixture
def repo(tmp_path) -> SQLiteJobRepository:
    db_path = tmp_path / "jobs_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    runner = MigrationRunner(conn)
    runner.apply_pending()
    return SQLiteJobRepository(conn)


def test_transition_matrix_matches_baseline():
    with open(BASELINES_DIR / "job_lifecycle_semantics.json", encoding="utf-8") as f:
        data = json.load(f)

    valid = data["valid_transitions"]
    for source_str, allowed_targets in valid.items():
        source = JobStatus(source_str)
        for target in JobStatus:
            if target.value in allowed_targets or target == source:
                assert can_transition(source, target) is True
                # Should not raise
                validate_transition(source, target)
            else:
                assert can_transition(source, target) is False
                with pytest.raises(DomainError) as exc:
                    validate_transition(source, target)
                assert exc.value.code == "INVALID_STATE"


def test_fencing_token_and_stale_worker_rejection(repo):
    # 1. Create a queued job
    job = JobRecord(job_id="job_001", job_type="fit_mmm", payload={"model": "mmm"})
    repo.create_job(job)

    # 2. Worker 1 claims job -> fence_token becomes 1
    claimed_w1 = repo.claim_next_job(worker_id="worker_1", lease_seconds=10)
    assert claimed_w1 is not None
    assert claimed_w1.status == JobStatus.RUNNING
    assert claimed_w1.lease_owner == "worker_1"
    assert claimed_w1.fence_token == 1

    # 3. Finish claim with stale fence_token 0 must be rejected
    with pytest.raises(DomainError) as exc:
        repo.finish_claim(
            job_id="job_001",
            worker_id="worker_1",
            fence_token=0,  # Stale fence token!
            status=JobStatus.SUCCEEDED,
            result={"status": "ok"},
        )
    assert exc.value.code == "STALE_JOB_CLAIM"

    # 4. Finish claim with matching worker and fence_token succeeds
    finished = repo.finish_claim(
        job_id="job_001",
        worker_id="worker_1",
        fence_token=1,
        status=JobStatus.SUCCEEDED,
        result={"status": "ok"},
    )
    assert finished.status == JobStatus.SUCCEEDED
    assert finished.result == {"status": "ok"}


def test_cooperative_cancellation_flow(repo):
    # Create and claim job
    job = JobRecord(job_id="job_002", job_type="fit_mmm", payload={})
    repo.create_job(job)
    claimed = repo.claim_next_job(worker_id="worker_1", lease_seconds=30)
    assert claimed.status == JobStatus.RUNNING

    # User requests cancellation
    cancelling_record = repo.request_cancellation("job_002")
    assert cancelling_record.status == JobStatus.CANCELLING

    # Worker attempts to finish as SUCCEEDED -> must fail with JOB_CANCELLED
    with pytest.raises(DomainError) as exc:
        repo.finish_claim(
            job_id="job_002",
            worker_id="worker_1",
            fence_token=claimed.fence_token,
            status=JobStatus.SUCCEEDED,
        )
    assert exc.value.code == "JOB_CANCELLED"

    # Worker finishes as CANCELLED -> succeeds
    cancelled = repo.finish_claim(
        job_id="job_002",
        worker_id="worker_1",
        fence_token=claimed.fence_token,
        status=JobStatus.CANCELLED,
    )
    assert cancelled.status == JobStatus.CANCELLED
