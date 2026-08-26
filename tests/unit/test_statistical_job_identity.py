"""Unit tests for statistical job identity and semantic idempotency hashing."""

from __future__ import annotations

from marketing_mcp.jobs.idempotency import (
    compute_semantic_idempotency_key,
)
from marketing_mcp.jobs.types import StatisticalJobType


def test_statistical_job_types_defined():
    assert StatisticalJobType.MMM_FIT.value == "mmm.fit"
    assert StatisticalJobType.MMM_CALIBRATE.value == "mmm.calibrate"
    assert StatisticalJobType.CLV_FIT_PURCHASE.value == "clv.fit_purchase"


def test_semantic_idempotency_key_deterministic():
    input_a = {
        "dataset_id": "d1",
        "target_column": "sales",
        "channel_columns": ["facebook", "tv"],
        "request_id": "req-123",  # should be ignored
    }
    input_b = {
        "target_column": "sales",
        "channel_columns": ["facebook", "tv"],
        "dataset_id": "d1",
        "timestamp": "2026-08-26T12:00:00Z",  # should be ignored
    }

    key_a = compute_semantic_idempotency_key("tenant_1", "mmm.fit", input_a)
    key_b = compute_semantic_idempotency_key("tenant_1", "mmm.fit", input_b)
    assert key_a == key_b

    # Different tenant produces different key
    key_other_tenant = compute_semantic_idempotency_key("tenant_2", "mmm.fit", input_a)
    assert key_a != key_other_tenant

    # Changed semantic configuration produces different key
    input_changed = dict(input_a)
    input_changed["channel_columns"] = ["facebook", "tv", "search"]
    key_changed = compute_semantic_idempotency_key("tenant_1", "mmm.fit", input_changed)
    assert key_a != key_changed
