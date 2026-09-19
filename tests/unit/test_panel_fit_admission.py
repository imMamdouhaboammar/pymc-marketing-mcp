"""Test panel dimensions propagation and admission in submit_fit_mmm_job (P0 regression)."""

from __future__ import annotations

import asyncio
import json

import numpy as np
import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.server import create_server
from marketing_mcp.schemas.models import FitMMMInput
from marketing_mcp.security.principal import Principal


@pytest.fixture
def test_env(tmp_path):
    app = Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )
    principal = Principal(
        subject="analyst",
        tenant_id="tenant_panel",
        scopes=frozenset({"marketing:read", "marketing:model", "marketing:decide"}),
        auth_type="api_key",
    )
    server = create_server(app, context_provider=lambda: type("Context", (), {"principal": principal})())
    return app, server, principal


async def _call_tool(server, tool: str, args: dict) -> dict:
    res = await server.call_tool(tool, args)
    item = res[0] if isinstance(res, list) else getattr(res, "content", [None])[0]
    text = getattr(item, "text", None) or str(item)
    return json.loads(text)


@pytest.mark.anyio
async def test_submit_fit_mmm_job_forwards_panel_dims(test_env):
    """P0 Regression Test: Panel dataset with duplicate dates across countries must be admitted

    when dims=['country_code'] is provided in FitMMMInput.
    """
    app, server, principal = test_env

    # Panel dataset: 60 dates x 2 countries = 120 rows (> 52 required periods) with variance.
    # Without dims, dates have duplicate keys. With dims=['country_code'], [date, country_code] is unique.
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=60, freq="D").strftime("%Y-%m-%d").tolist()
    rows = []
    for d in dates:
        for country in ["US", "UK"]:
            sp = float(np.random.uniform(50.0, 250.0))
            sa = float(sp * 2.5 + np.random.uniform(10.0, 50.0))
            rows.append({
                "date": d,
                "country_code": country,
                "sales": round(sa, 2),
                "spend": round(sp, 2),
            })
    df = pd.DataFrame(rows)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    registered = app.datasets.register_bytes(
        csv_bytes,
        format="csv",
        filename="panel_test.csv",
        principal=principal,
    )
    dataset_id = registered.dataset_id

    # 1. validate_dataset with dims must pass
    val_resp = await _call_tool(
        server,
        "validate_dataset",
        {
            "dataset_id": dataset_id,
            "date_column": "date",
            "target_column": "sales",
            "channel_columns": ["spend"],
            "dims": ["country_code"],
        },
    )
    assert "summary" in val_resp
    assert val_resp["summary"]["valid_for_modeling"] is True

    # 2. submit_fit_mmm_job with dims must succeed admission without DATASET_VALIDATION_FAILED
    fit_config = FitMMMInput(
        dataset_id=dataset_id,
        date_column="date",
        target_column="sales",
        channel_columns=["spend"],
        dims=["country_code"],
        sampler={"draws": 50, "tune": 50, "chains": 2},
    )

    submit_resp = await _call_tool(
        server,
        "submit_fit_mmm_job",
        {"config": fit_config.model_dump()},
    )

    # Must NOT fail with DATASET_VALIDATION_FAILED
    assert "error" not in submit_resp, f"Expected successful admission but got error: {submit_resp.get('error')}"
    assert "summary" in submit_resp
    job_summary = submit_resp["summary"]
    job_id = job_summary["job_id"]

    # 3. Payload must retain dims
    job = app.jobs.get_job(job_id, principal=principal)
    assert job.payload["dims"] == ["country_code"]

    # 4. Wait for background job to finish and assert checkpoint & state contracts
    import time
    start_t = time.time()
    while time.time() - start_t < 90:
        st = app.jobs.get_job(job_id, principal=principal)
        if st.status.is_terminal:
            break
        await asyncio.sleep(0.2)

    assert st.status.value == "succeeded"
    checkpoints = app.jobs.get_checkpoints(job_id, principal=principal)
    stages = [cp.stage for cp in checkpoints]
    # Checkpoint named diagnostics_completed MUST NOT exist
    assert "diagnostics_completed" not in stages, f"Deceptive checkpoint found in stages: {stages}"
    assert "fit_completed" in stages, f"Expected fit_completed in stages: {stages}"

    # Model record must be not_diagnosed and retain dims across all configs
    model_id = st.result["model_id"]
    model_rec = app.metadata.get_model(model_id, tenant_id=principal.tenant_id)
    assert model_rec["validation_state"] == "not_diagnosed"
    assert model_rec.get("diagnostics") is None
    assert model_rec["config"]["dims"] == ["country_code"]
    assert model_rec["requested_config"]["dims"] == ["country_code"]
    assert model_rec["resolved_config"]["dims"] == ["country_code"]
    assert model_rec["effective_config"]["dims"] == ["country_code"]

    # 5. Calling diagnose_mmm changes validation_state to approved/caution and populates diagnostics
    diag_resp = await _call_tool(server, "diagnose_mmm", {"model_id": model_id})
    assert "summary" in diag_resp
    assert diag_resp["summary"]["model_id"] == model_id
    updated_model = app.metadata.get_model(model_id, tenant_id=principal.tenant_id)
    assert updated_model["validation_state"] in ("approved", "approved_with_caution", "rejected")
    assert updated_model["validation_state"] != "not_diagnosed"
    assert updated_model["diagnostics"] is not None
