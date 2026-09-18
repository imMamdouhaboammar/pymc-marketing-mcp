"""Integration tests verifying Data Intelligence Engine integration with MCP services and tools."""

from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.intelligence.contracts.semantics import SemanticRole
from marketing_mcp.mcp.server import create_server


@pytest.fixture
def test_app(tmp_path):
    settings = Settings(
        data_dir=tmp_path / "data",
        artifact_dir=tmp_path / "artifacts",
        metadata_db=tmp_path / "meta.db",
        max_dataset_mb=10,
    )
    return Application(settings)


def test_inspect_dataset_returns_semantic_contract_and_clarifications(test_app, tmp_path):
    """Verifies inspect_dataset populates semantic contract and clarifies ambiguous targets."""
    f = tmp_path / "ambiguous_targets.csv"
    dates = pd.date_range("2025-01-06", periods=60, freq="W-MON")
    df = pd.DataFrame({
        "date": dates,
        "platform_revenue_usd": [5000.0 + i * 50 for i in range(60)],
        "crm_revenue_usd": [4800.0 + i * 48 for i in range(60)],
        "google_spend": [1000.0 + i * 10 for i in range(60)],
        "meta_spend": [800.0 + i * 8 for i in range(60)],
    })
    df.to_csv(f, index=False)
    reg = test_app.datasets.register_file(f)

    # 1. Initial inspection without overrides
    inspection = test_app.datasets.inspect(reg.dataset_id)
    assert inspection.mmm_candidate is True
    assert inspection.semantic_contract is not None
    assert len(inspection.clarification_requests) > 0
    q = inspection.clarification_requests[0]
    assert "platform_revenue_usd" in q["options"]
    assert "crm_revenue_usd" in q["options"]

    # 2. Inspection with user override resolving ambiguity
    overridden = test_app.datasets.inspect(
        reg.dataset_id,
        user_overrides={"crm_revenue_usd": {"role": SemanticRole.TARGET}},
    )
    assert overridden.semantic_contract is not None
    assert overridden.semantic_contract["target"]["column"] == "crm_revenue_usd"
    assert overridden.semantic_contract["target"]["user_overridden"] is True


def test_validate_dataset_enforces_intelligence_gates_on_mixed_objectives(test_app, tmp_path):
    """Verifies validate_dataset flags non-suitable datasets with mixed conversion semantics."""
    f = tmp_path / "mixed_obj.csv"
    dates = pd.date_range("2025-01-06", periods=30, freq="W-MON").tolist() * 2
    df = pd.DataFrame({
        "date": dates,
        "objective": ["Sales"] * 30 + ["Awareness"] * 30,
        "revenue": [5000.0] * 30 + [0.0] * 30,
        "meta_spend": [500.0] * 60,
        "google_spend": [400.0] * 60,
    })
    df.to_csv(f, index=False)
    reg = test_app.datasets.register_file(f)

    val = test_app.datasets.validate(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta_spend", "google_spend"],
        control_columns=[],
    )
    finding_codes = [f.code for f in val.findings]
    assert "MIXED_CONVERSION_SEMANTICS" in finding_codes


def test_validate_dataset_generates_modeling_contract_on_clean_data(test_app, tmp_path):
    """Verifies validate_dataset attaches validated modeling contract for clean datasets."""
    f = tmp_path / "clean_mmm.csv"
    dates = pd.date_range("2025-01-06", periods=65, freq="W-MON")
    df = pd.DataFrame({
        "date": dates,
        "revenue": [50000.0 + i * 100 for i in range(65)],
        "meta_spend": [2000.0 + i * 15 for i in range(65)],
        "google_spend": [1500.0 + i * 10 for i in range(65)],
    })
    df.to_csv(f, index=False)
    reg = test_app.datasets.register_file(f)

    val = test_app.datasets.validate(
        dataset_id=reg.dataset_id,
        date_column="date",
        target_column="revenue",
        channel_columns=["meta_spend", "google_spend"],
        control_columns=[],
    )
    assert val.valid_for_modeling is True
    assert val.modeling_contract is not None
    assert val.modeling_contract["target_column"] == "revenue"
    assert val.modeling_contract["channel_columns"] == ["meta_spend", "google_spend"]
    assert val.modeling_contract["frequency"] == "weekly"


def test_mcp_inspect_dataset_tool_integration(test_app, tmp_path):
    """Verifies the MCP inspect_dataset tool returns full envelope with contract evidence."""
    f = tmp_path / "test_mcp.csv"
    df = pd.DataFrame({
        "date": pd.date_range("2025-01-06", periods=55, freq="W-MON"),
        "sales": [10000.0 + i * 10 for i in range(55)],
        "ad_spend": [500.0 + i * 5 for i in range(55)],
    })
    df.to_csv(f, index=False)
    reg = test_app.datasets.register_file(f)

    server = create_server(test_app)

    async def _run():
        res = await server.call_tool("inspect_dataset", {"dataset_id": reg.dataset_id})
        return res

    result = asyncio.run(_run())
    # Envelope structure verification
    assert result is not None
    import json
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    assert item is not None
    text_content = getattr(item, "text", None) or str(item)
    data = json.loads(text_content)
    assert "summary" in data
    assert "evidence" in data
    assert "semantic_contract" in data["evidence"]
    assert data["evidence"]["semantic_contract"]["target"]["column"] == "sales"
