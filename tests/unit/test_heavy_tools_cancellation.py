"""Unit tests verifying operation guard tracking and cooperative cancellation of direct heavy operations."""

from __future__ import annotations

import asyncio
import sqlite3
import threading

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.operation_guard import ConcurrencyCancellationGuard
from marketing_mcp.schemas.models import FitMMMInput
from marketing_mcp.security.principal import Principal
from marketing_mcp.services.modeling_service import ModelingService
from marketing_mcp.storage.metadata import SQLiteMetadataStore


@pytest.mark.anyio
async def test_operation_guard_cancels_event_on_task_cancellation():
    guard = ConcurrencyCancellationGuard()
    captured_op = None

    async def long_running_coro():
        nonlocal captured_op
        async with guard.track("fit_mmm", principal=None, details={"test": True}) as op:
            captured_op = op
            await asyncio.sleep(5.0)

    task = asyncio.create_task(long_running_coro())
    await asyncio.sleep(0.05)
    assert captured_op is not None
    assert captured_op.is_cancelled is False

    # Simulate client disconnect / timeout
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    # Cooperative cancellation event must be set immediately
    assert captured_op.is_cancelled is True
    assert captured_op.status == "cancelled"
    assert len(guard.list_active()) == 0


def test_modeling_service_aborts_when_cancel_event_set(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from marketing_mcp.storage.migrations import MigrationRunner
    MigrationRunner(conn).apply_pending()
    metadata = SQLiteMetadataStore(tmp_path / "meta.db")
    metadata.put_dataset({
        "dataset_id": "ds_1",
        "path": "/tmp/ds.csv",
        "format": "csv",
        "rows": 100,
        "created_at": "2026-01-01T00:00:00Z",
        "fingerprint": "abc",
        "tenant_id": "t1",
        "owner": "user",
    })

    # Mock datasets, artifacts, and adapter
    class MockDatasets:
        def validate(self, *args, **kwargs):
            from marketing_mcp.schemas.models import DatasetValidationResult
            return DatasetValidationResult(dataset_id="ds_1", findings=[], valid_for_modeling=True)
        def load(self, *args, **kwargs):
            import pandas as pd
            return pd.DataFrame()

    class MockArtifacts:
        def put_file(self, *args, **kwargs):
            from marketing_mcp.repositories.models import ArtifactRef
            return ArtifactRef(id="art_1", uri="file:///tmp/art", size_bytes=100, content_type="test")

    class MockAdapter:
        def versions(self):
            return {"pymc": "5.0"}
        def fit(self, *args, **kwargs):
            pass

    service = ModelingService(metadata, MockArtifacts(), MockDatasets(), MockAdapter)

    cancel_event = threading.Event()
    cancel_event.set()

    principal = Principal(subject="user", tenant_id="t1", scopes=frozenset({"marketing:model"}), auth_type="api_key")
    fit_input = FitMMMInput(
        dataset_id="ds_1",
        date_column="date",
        target_column="sales",
        channel_columns=["spend"],
    )

    with pytest.raises(DomainError) as exc_info:
        service.fit(fit_input, principal=principal, cancel_event=cancel_event)

    assert exc_info.value.code == "OPERATION_CANCELLED"
    models = metadata.list_models(tenant_id="t1")
    assert len(models) == 1
    assert models[0]["status"] == "cancelled"


@pytest.mark.anyio
async def test_operation_guard_run_tracked_executor_rejects_duplicate():
    """P1 Item 5: ConcurrencyCancellationGuard.run_tracked_executor blocks duplicate runs
    with the same identity_key while the underlying executor is still running.
    """
    guard = ConcurrencyCancellationGuard()
    release = threading.Event()

    def slow_worker(cancel_event):
        release.wait(5.0)
        return {"done": True}

    # Start first operation in background
    task1 = asyncio.create_task(
        guard.run_tracked_executor(
            "fit_mmm",
            slow_worker,
            identity_key="unique-fit-key",
        )
    )

    # Wait for first operation to start and register
    for _ in range(50):
        if len(guard.list_active()) == 1:
            break
        await asyncio.sleep(0.01)

    assert len(guard.list_active()) == 1

    # Attempt second operation with same identity_key while first is running
    with pytest.raises(DomainError) as exc_info:
        await guard.run_tracked_executor(
            "fit_mmm",
            lambda cancel_event: {"done": True},
            identity_key="unique-fit-key",
        )
    assert exc_info.value.code == "OPERATION_ALREADY_RUNNING"

    # Finish first operation
    release.set()
    res1 = await task1
    assert res1 == {"done": True}

    # Once finished, guard is cleared
    assert len(guard.list_active()) == 0

    # Now another operation with the same key is permitted
    res2 = await guard.run_tracked_executor(
        "fit_mmm",
        lambda cancel_event: {"second": True},
        identity_key="unique-fit-key",
    )
    assert res2 == {"second": True}


def test_decision_service_aborts_when_cancel_event_set(tmp_path):
    """P1 Item 7: DecisionService checks cancel_event before expensive compute,
    after compute, and before persisting scenario mutations.
    """
    from marketing_mcp.schemas.models import (
        BudgetOptimizationInput,
        BudgetSimulationInput,
        FlightingOptimizationInput,
    )
    from marketing_mcp.services.decision_service import DecisionService

    metadata = SQLiteMetadataStore(tmp_path / "meta_dec.db")
    metadata.put_model({
        "model_id": "m1",
        "dataset_id": "ds1",
        "validation_state": "approved",
        "status": "ready",
        "tenant_id": "t1",
        "config": {"channel_columns": ["ch1", "ch2"]},
    })

    class MockModeling:
        def status(self, model_id, principal=None):
            from marketing_mcp.repositories.models import ModelRecord

            return ModelRecord(
                model_id=model_id,
                dataset_id="ds1",
                status="ready",
                validation_state="approved",
            )

        def load_model(self, model_id, principal=None):
            class DummyModel:
                pass

            class DummyRec:
                validation_state = "approved"

            return DummyModel(), DummyRec()

    dec_service = DecisionService(metadata, MockModeling())
    cancel_event = threading.Event()
    cancel_event.set()

    # 1. Budget optimization
    with pytest.raises(DomainError) as exc1:
        dec_service.optimize(
            BudgetOptimizationInput(
                model_id="m1", budget=1000.0, planning_periods=4
            ),
            cancel_event=cancel_event,
        )
    assert exc1.value.code == "OPERATION_CANCELLED"

    # 2. Flighting optimization
    with pytest.raises(DomainError) as exc2:
        dec_service.optimize_flighting(
            FlightingOptimizationInput(
                model_id="m1", total_budget=5000.0, planning_weeks=4
            ),
            cancel_event=cancel_event,
        )
    assert exc2.value.code == "OPERATION_CANCELLED"

    # 3. Budget simulation
    from marketing_mcp.schemas.models import BudgetChange

    with pytest.raises(DomainError) as exc3:
        dec_service.simulate(
            BudgetSimulationInput(
                model_id="m1",
                changes={"ch1": BudgetChange(type="absolute", value=500.0)},
            ),
            cancel_event=cancel_event,
        )
    assert exc3.value.code == "OPERATION_CANCELLED"


