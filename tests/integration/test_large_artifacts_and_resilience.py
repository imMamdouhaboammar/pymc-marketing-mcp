from __future__ import annotations

import asyncio
import hashlib
import tempfile
import time
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from marketing_mcp.app import Application
from marketing_mcp.cli import create_http_app
from marketing_mcp.config import Settings
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.mcp.server import create_server
from marketing_mcp.storage.artifacts import LocalArtifactStore
from marketing_mcp.storage.gc import StorageGarbageCollector


@pytest.fixture
def app_instance(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "metadata.db",
        ingest_dir=tmp_path / "inbox",
        auth_enabled=False,
    )
    return Application(settings)


def test_chunked_artifact_streaming_and_zero_ram_materialize(tmp_path):
    store = LocalArtifactStore(tmp_path / "artifacts")

    # Create a simulated 5MB binary artifact file
    source_file = tmp_path / "large_model.nc"
    data = b"MCMC_TRACE_CHUNK_" * (1024 * 256)  # ~4.3 MB
    source_file.write_bytes(data)
    expected_sha256 = hashlib.sha256(data).hexdigest()

    # Put file using stream hashing
    ref = store.put_file(source_file, content_type="application/x-netcdf", owner="test_user", tenant_id="tenant_a")
    assert ref.sha256 == expected_sha256
    assert ref.size_bytes == len(data)

    # Test chunked reading
    chunks = list(store.read_chunks(ref, owner="test_user", tenant_id="tenant_a", chunk_size=512 * 1024))
    assert sum(len(c) for c in chunks) == len(data)
    assert hashlib.sha256(b"".join(chunks)).hexdigest() == expected_sha256

    # Test zero-RAM materialize using symlink
    with store.materialize(ref, owner="test_user", tenant_id="tenant_a", suffix=".nc") as path:
        assert path.exists()
        assert path.name.endswith(".nc")
        assert path.stat().st_size == len(data)


def test_http_streaming_endpoint_with_range_requests(app_instance):
    # Register an artifact in the store
    data = b"BAYESIAN_POSTERIOR_STREAM_TEST_DATA_" * 1000
    ref = app_instance.artifacts.put_bytes(
        data, content_type="application/octet-stream", owner="local", tenant_id=None
    )
    namespace = app_instance.artifacts._namespace("local", None)

    http_app = create_http_app(application=app_instance, settings=app_instance.settings)
    client = TestClient(http_app)

    # Full download
    resp = client.get(f"/artifacts/{namespace}/{ref.sha256}/download")
    assert resp.status_code == 200
    assert resp.content == data
    assert resp.headers["content-length"] == str(len(data))
    assert resp.headers["accept-ranges"] == "bytes"

    # HTTP Range request (first 100 bytes)
    range_resp = client.get(
        f"/artifacts/{namespace}/{ref.sha256}/download",
        headers={"Range": "bytes=0-99"},
    )
    assert range_resp.status_code == 206
    assert range_resp.content == data[:100]
    assert range_resp.headers["content-range"] == f"bytes 0-99/{len(data)}"
    assert range_resp.headers["content-length"] == "100"


def test_checkpoint_persistence_and_chronological_retrieval(app_instance):
    job_id = "job-test-cp-001"
    job = JobRecord(job_id=job_id, job_type="fit_mmm")
    app_instance.job_repo.create_job(job)

    # Record intermediate checkpoints
    app_instance.jobs.record_checkpoint(job_id, "dataset_validated", progress_percent=15.0)
    app_instance.jobs.record_checkpoint(job_id, "sampling_initialized", progress_percent=35.0)
    app_instance.jobs.record_checkpoint(
        job_id, "posterior_saved", progress_percent=90.0, state_data={"model_id": "mmm_recovered"}
    )

    checkpoints = app_instance.jobs.get_checkpoints(job_id)
    assert len(checkpoints) == 3
    assert checkpoints[0].stage == "dataset_validated"
    assert checkpoints[1].stage == "sampling_initialized"
    assert checkpoints[2].stage == "posterior_saved"

    latest = app_instance.jobs.get_latest_checkpoint(job_id)
    assert latest is not None
    assert latest.stage == "posterior_saved"
    assert latest.state_data["model_id"] == "mmm_recovered"


def test_crash_recovery_reconciles_completed_checkpoints_to_succeeded(app_instance):
    job_id = "job-crashed-before-reply"
    job = JobRecord(job_id=job_id, job_type="fit_mmm", status=JobStatus.RUNNING)
    app_instance.job_repo.create_job(job)

    # Simulate checkpoint saved right before server crashed/restarted
    app_instance.jobs.record_checkpoint(
        job_id,
        "posterior_saved",
        progress_percent=90.0,
        state_data={"model_id": "mmm_saved_before_crash", "result": {"model_id": "mmm_saved_before_crash"}},
    )

    # Simulate server boot recovery
    recovered_count = app_instance.job_repo.recover_stale_running_jobs()
    assert recovered_count >= 1

    recovered_job = app_instance.job_repo.get_job(job_id)
    assert recovered_job.status == JobStatus.SUCCEEDED
    assert recovered_job.result["model_id"] == "mmm_saved_before_crash"


def test_recover_execution_state_and_resumption(app_instance):
    job_id = "job-interrupted-sampling"
    job = JobRecord(job_id=job_id, job_type="fit_mmm", status=JobStatus.FAILED)
    app_instance.job_repo.create_job(job)
    app_instance.jobs.record_checkpoint(job_id, "sampling_initialized", progress_percent=30.0)

    # Recover state query
    state = app_instance.jobs.recover_job_state(job_id)
    assert state["job_id"] == job_id
    assert state["can_resume"] is True
    assert state["recommended_action"] == "resume_job"
    assert state["latest_checkpoint"]["stage"] == "sampling_initialized"


def test_export_artifact_to_sandbox_and_garbage_collection(app_instance, tmp_path):
    mcp = create_server(app_instance)

    # Create dummy artifact
    data = b"MCMC_MODEL_BINARY_ARVIZ_NC_CONTENT"
    ref = app_instance.artifacts.put_bytes(data, content_type="application/x-netcdf", owner="local", tenant_id=None)

    # 1. Export artifact to sandbox
    export_handler = None
    tools = asyncio.run(mcp.list_tools())
    for t in tools:
        if t.name == "export_artifact_to_sandbox":
            export_handler = t

    assert export_handler is not None

    export_res = app_instance.artifacts.export_to_sandbox(
        ref, owner="local", tenant_id=None, export_name="test_model.nc"
    )
    assert "download_url" in export_res
    assert "sandbox_curl_command" in export_res
    assert "python_snippet" in export_res
    assert export_res["sha256"] == ref.sha256
    assert "curl -fSL" in export_res["sandbox_curl_command"]

    # 2. Test Garbage Collection
    # Create fake /tmp leftover directory
    fake_temp = Path(tempfile.gettempdir()) / f"marketing-mcp-fit-{int(time.time())}"
    fake_temp.mkdir(parents=True, exist_ok=True)
    (fake_temp / "scratch.nc").write_bytes(b"temp_scratch_data")

    gc = StorageGarbageCollector(app_instance.artifacts, metadata_conn=app_instance.metadata.conn)
    report = gc.cleanup(older_than_hours=0, dry_run=False)

    assert report["deleted_files_count"] >= 1
    assert report["freed_bytes"] > 0
    assert not fake_temp.exists()
