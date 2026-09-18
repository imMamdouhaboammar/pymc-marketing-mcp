"""Unit tests for Agent Insights & Interaction Logging service and storage (TDD)."""

from __future__ import annotations

import sqlite3

import pytest

from marketing_mcp.security.principal import Principal
from marketing_mcp.storage.metadata import SQLiteMetadataStore
from marketing_mcp.storage.migrations import MigrationRunner


@pytest.fixture
def db_conn(tmp_path):
    db_path = tmp_path / "test_insights.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    runner = MigrationRunner(conn)
    runner.apply_pending()
    yield conn
    conn.close()


def test_migration_005_creates_agent_insights_table(db_conn):
    """Assert migration version is at least 5 and agent_insights table exists."""
    runner = MigrationRunner(db_conn)
    assert runner.current_version() >= 5

    # Check columns in agent_insights table
    columns = {row[1] for row in db_conn.execute("PRAGMA table_info(agent_insights)").fetchall()}
    expected = {
        "insight_id",
        "tenant_id",
        "agent_id",
        "category",
        "severity",
        "summary",
        "details",
        "model_id",
        "dataset_id",
        "tags",
        "created_at",
    }
    assert expected.issubset(columns)


def test_metadata_store_insight_crud_and_tenant_isolation(tmp_path):
    """Assert SQLiteMetadataStore put_insight and list_insights strictly enforce tenant isolation."""
    store = SQLiteMetadataStore(tmp_path / "meta.db")

    insight_tenant_a = {
        "insight_id": "ins_001",
        "tenant_id": "tenant_a",
        "agent_id": "antigravity",
        "category": "eda_finding",
        "severity": "info",
        "summary": "TikTok channel shows strong seasonality on weekends",
        "details": "Autocorrelation at lag 7 is 0.78",
        "model_id": "mod_123",
        "dataset_id": "ds_456",
        "tags": ["seasonality", "tiktok"],
        "created_at": "2026-09-17T12:00:00Z",
    }
    store.put_insight(insight_tenant_a)

    insight_tenant_b = {
        "insight_id": "ins_002",
        "tenant_id": "tenant_b",
        "agent_id": "cursor",
        "category": "diagnostic_warning",
        "severity": "warning",
        "summary": "Divergences detected in TV channel prior",
        "details": "15 divergent transitions encountered during sampling",
        "model_id": "mod_999",
        "dataset_id": "ds_888",
        "tags": ["diagnostics", "divergences"],
        "created_at": "2026-09-17T13:00:00Z",
    }
    store.put_insight(insight_tenant_b)

    # Tenant A must only see Tenant A's insights
    results_a = store.list_insights(tenant_id="tenant_a")
    assert len(results_a) == 1
    assert results_a[0]["insight_id"] == "ins_001"
    assert results_a[0]["summary"] == "TikTok channel shows strong seasonality on weekends"

    # Tenant B must only see Tenant B's insights
    results_b = store.list_insights(tenant_id="tenant_b")
    assert len(results_b) == 1
    assert results_b[0]["insight_id"] == "ins_002"

    # Tenant C sees nothing
    assert len(store.list_insights(tenant_id="tenant_c")) == 0

    # Filter by model_id
    filtered = store.list_insights(tenant_id="tenant_a", model_id="mod_123")
    assert len(filtered) == 1
    assert store.list_insights(tenant_id="tenant_a", model_id="nonexistent") == []


def test_insight_service_record_and_query(tmp_path):
    """Assert InsightService handles model conversion, tagging, and validation."""
    from marketing_mcp.schemas.models import QueryInsightsInput, RecordInsightInput
    from marketing_mcp.services.insight_service import InsightService

    store = SQLiteMetadataStore(tmp_path / "meta_svc.db")
    service = InsightService(store)

    principal_a = Principal(
        subject="usr_01",
        auth_type="api_key",
        tenant_id="acme_corp",
        scopes=frozenset({"marketing:read", "marketing:model"}),
    )

    inp = RecordInsightInput(
        category="diagnostic_warning",
        summary="High divergence on Search adstock parameter",
        details="Try tightening the prior on alpha to HalfNormal(0.5)",
        model_id="mmm_model_42",
        agent_id="claude-code",
        severity="warning",
        tags=["adstock", "search", "prior"],
    )

    created = service.record_insight(inp, principal=principal_a)
    assert created["insight_id"].startswith("ins_")
    assert created["tenant_id"] == "acme_corp"
    assert created["agent_id"] == "claude-code"
    assert created["category"] == "diagnostic_warning"
    assert created["severity"] == "warning"
    assert created["tags"] == ["adstock", "search", "prior"]

    # Query back
    q = QueryInsightsInput(model_id="mmm_model_42")
    records = service.list_insights(q, principal=principal_a)
    assert len(records) == 1
    assert records[0]["insight_id"] == created["insight_id"]
    assert records[0]["summary"] == "High divergence on Search adstock parameter"
