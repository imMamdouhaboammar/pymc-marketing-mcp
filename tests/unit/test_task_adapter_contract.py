"""Unit tests for ProtocolTaskAdapter and UnsupportedTasksExtensionAdapter."""

from __future__ import annotations

import pytest

from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.mcp.task_adapter import (
    UnsupportedTasksExtensionAdapter,
)
from marketing_mcp.security.principal import Principal


def test_unsupported_tasks_adapter_does_not_advertise():
    adapter = UnsupportedTasksExtensionAdapter()
    assert adapter.supported is False

    # Calling advertise on a dummy server is a safe no-op
    adapter.advertise_if_supported(object())

    # Creating protocol handle produces standard structure
    rec = JobRecord(job_id="job-123", job_type="mmm.fit", status=JobStatus.QUEUED)
    handle = adapter.to_protocol_handle(rec)
    assert handle["taskId"] == "job-123"
    assert handle["status"] == "queued"

    # Updating raises NotImplementedError
    p = Principal(subject="u1", auth_type="stdio")
    with pytest.raises(NotImplementedError):
        adapter.apply_protocol_update("job-123", {}, p)
