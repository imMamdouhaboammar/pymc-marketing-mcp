from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.jobs.models import JobRecord, JobStatus


def test_real_subprocess_worker_crash_and_lease_recovery(tmp_path: Path):
    """Subprocess crash recovery test.

    Verifies that when an external worker process dies abruptly (SIGKILL),
    its expired lease is reaped and the job does NOT remain 'running' forever.
    """
    db_path = tmp_path / "crash_test.db"
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=db_path,
        ingest_dir=tmp_path / "inbox",
        auth_enabled=False,
    )
    app = Application(settings)

    job_id = "job_crash_test_001"
    rec = JobRecord(
        job_id=job_id,
        job_type="fit_mmm",
        status=JobStatus.QUEUED,
        owner="test_runner",
        tenant_id="tenant_x",
        payload={"sample_size": 100},
        max_attempts=1,  # Exhaust retries on first failure to test terminal transition
    )
    app.jobs.repo.create_job(rec)

    # Python script to run as separate OS subprocess
    worker_script = f"""
import sys
import time
from pathlib import Path
from marketing_mcp.storage.metadata import SQLiteMetadataStore
from marketing_mcp.jobs.repository import SQLiteJobRepository

store = SQLiteMetadataStore("{db_path}")
repo = SQLiteJobRepository(store.conn)

# Claim job with 2-second lease
job = repo.claim_next_job(tenant_id="tenant_x", worker_id="subprocess_worker_pid", lease_seconds=2)
if not job:
    sys.exit(1)

# Signal to parent that job is claimed and running
print("CLAIMED", flush=True)

# Simulate active work without exiting
while True:
    time.sleep(0.1)
"""

    env = dict(os.environ)
    env["PYTHONPATH"] = "src"

    proc = subprocess.Popen(
        [sys.executable, "-c", worker_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        # Wait until subprocess claims job and starts running
        line = proc.stdout.readline().strip()
        assert line == "CLAIMED", f"Worker failed to claim job: {proc.stderr.read()}"

        # Verify in parent DB that job is running with lease
        running_job = app.jobs.repo.get_job(job_id, tenant_id="tenant_x")
        assert running_job.status == JobStatus.RUNNING
        assert running_job.lease_owner == "subprocess_worker_pid"

        # FORCIBLY KILL WORKER SUBPROCESS (simulating sudden container crash / SIGKILL)
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait()

        # Wait for lease to expire (lease was 2.0 seconds)
        time.sleep(2.5)

        # Run stale lease recovery in parent / separate process
        recovered = app.jobs.repo.recover_stale_running_jobs()
        assert recovered >= 1, "Expected recover_stale_running_jobs to recover at least 1 job"

        # Verify job is no longer 'running'
        final_job = app.jobs.repo.get_job(job_id, tenant_id="tenant_x")
        assert final_job.status != JobStatus.RUNNING
        assert final_job.status == JobStatus.FAILED
        assert final_job.error is not None
        assert final_job.error.get("code") in ("WORKER_ATTEMPTS_EXHAUSTED", "WORKER_LEASE_EXPIRED")
        assert final_job.lease_owner is None

    finally:
        if proc.poll() is None:
            proc.kill()
