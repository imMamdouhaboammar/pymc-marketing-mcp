"""Integration tests for remote data ingestion, error diagnostics, and batch model validation."""

from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import ExecutionContext, stdio_context_provider
from marketing_mcp.mcp.server import create_server


def _call(server, tool, args):
    result = asyncio.run(server.call_tool(tool, args))
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    if item is None:
        raise AssertionError(f"unexpected call_tool result: {result!r}")
    text = getattr(item, "text", None) or str(item)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


@pytest.fixture
def test_server(tmp_path):
    data_dir = tmp_path / "data"
    artifact_dir = tmp_path / "artifacts"
    metadata_db = tmp_path / "metadata.db"
    inbox_dir = tmp_path / "inbox"
    data_dir.mkdir(parents=True)
    artifact_dir.mkdir(parents=True)
    inbox_dir.mkdir(parents=True)

    # Seed an inbox file
    (inbox_dir / "sample_inbox.csv").write_text("date,revenue,spend\n2026-01-01,100,50\n")

    settings = Settings(
        data_dir=data_dir,
        artifact_dir=artifact_dir,
        metadata_db=metadata_db,
        ingest_dir=inbox_dir,
        auth_enabled=False,
    )
    app = Application(settings)
    return create_server(app, context_provider=stdio_context_provider), app, inbox_dir


def test_register_dataset_direct_csv_content(test_server):
    server, app, _ = test_server
    csv_text = "date,revenue,meta_spend,google_spend\n2026-01-01,1000,200,300\n2026-01-02,1200,250,350\n"
    res = _call(server, "register_dataset", {"content": csv_text, "filename": "campaign_data.csv"})

    assert "summary" in res, f"Expected summary in response: {res}"
    dataset_id = res["summary"]["dataset_id"]
    assert dataset_id.startswith("dataset_")
    assert res["summary"]["rows"] == 2
    assert res["summary"]["format"] == "csv"

    # Verify inspect_dataset works immediately on the registered ID
    inspect_res = _call(server, "inspect_dataset", {"dataset_id": dataset_id})
    assert "summary" in inspect_res
    assert inspect_res["summary"]["rows"] == 2


def test_register_dataset_direct_base64_content(test_server):
    server, app, _ = test_server
    csv_text = "date,revenue,meta\n2026-01-01,500,100\n"
    b64_content = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")

    res = _call(server, "register_dataset", {"content_base64": b64_content, "filename": "uploaded.csv"})
    assert "summary" in res
    assert res["summary"]["rows"] == 1
    assert res["summary"]["format"] == "csv"


def test_register_dataset_client_sandbox_error_diagnostics(test_server):
    server, app, _ = test_server
    sandbox_path = "/mnt/user-data/uploads/complex_ads_sample_data.csv"
    res = _call(server, "register_dataset", {"path": sandbox_path})

    assert "error" in res
    err = res["error"]
    assert err["code"] == "CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE"
    assert sandbox_path in err["message"]
    assert err["evidence"]["attempted_path"] == sandbox_path
    assert "content" in err["next_action"]
    assert "content_base64" in err["next_action"]


def test_register_dataset_missing_server_file_echoes_path(test_server):
    server, app, _ = test_server
    missing_file = "nonexistent_ads.csv"
    res = _call(server, "register_dataset", {"path": missing_file})

    assert "error" in res
    err = res["error"]
    assert err["code"] == "FILE_NOT_FOUND"
    assert missing_file in err["message"]
    assert missing_file in err["evidence"]["attempted_path"]
    assert err["next_action"] is not None


def test_list_datasets_discovery(test_server):
    server, app, inbox = test_server
    # 1. Initially lists the seeded inbox file and 0 registered
    res = _call(server, "list_datasets", {})
    assert "summary" in res
    assert res["summary"]["total_registered"] == 0
    assert res["summary"]["total_inbox_files"] == 1
    assert res["evidence"]["inbox_files"][0]["name"] == "sample_inbox.csv"

    # 2. Register one dataset via content
    _call(server, "register_dataset", {"content": "date,sales\n2026-01-01,10\n"})

    # 3. Now lists 1 registered dataset
    res2 = _call(server, "list_datasets", {})
    assert res2["summary"]["total_registered"] == 1
    assert len(res2["evidence"]["registered_datasets"]) == 1


def test_compare_models_reports_all_missing_ids(test_server):
    server, app, _ = test_server
    fake_ids = ["mdl_fake_1", "mdl_fake_2", "mdl_fake_3"]
    res = _call(server, "compare_models", {"input": {"model_ids": fake_ids}})

    assert "error" in res
    err = res["error"]
    assert err["code"] == "MODEL_NOT_FOUND"
    # All 3 missing models must be reported in evidence
    assert err["evidence"]["missing_model_ids"] == fake_ids
    assert err["next_action"] is not None


def test_metadata_not_found_populates_evidence_and_next_action(test_server):
    server, app, _ = test_server
    res = _call(server, "inspect_dataset", {"dataset_id": "ds_nonexistent_999"})

    assert "error" in res
    err = res["error"]
    assert err["code"] == "DATASET_NOT_FOUND"
    assert "ds_nonexistent_999" in err["message"]
    assert err["evidence"]["resource_id"] == "ds_nonexistent_999"
    assert err["next_action"] is not None


def test_decision_gate_blocks_undiagnosed_model(test_server):
    server, app, _ = test_server
    # Direct optimize_budget with missing or undiagnosed model
    res = _call(server, "optimize_budget", {"config": {"model_id": "mdl_missing", "budget": 10000}})
    assert "error" in res
    err = res["error"]
    assert err["code"] == "MODEL_NOT_FOUND"
    assert err["evidence"] is not None
    assert err["next_action"] is not None
