from __future__ import annotations

import pandas as pd
import pytest

from marketing_mcp.intelligence.contracts.profile import ColumnProfile, MissingnessDetail, NumericDistribution
from marketing_mcp.intelligence.contracts.semantics import SemanticRole
from marketing_mcp.intelligence.semantics.channels import infer_channel_column
from marketing_mcp.storage.metadata import SQLiteMetadataStore
from marketing_mcp.storage.migrations import MigrationRunner


def test_token_boundary_inference_prevents_false_positives():
    """Verify that token boundary matching prevents substring false positives (e.g. 'li' in 'client')."""
    dummy_series = pd.Series([10.0, 20.0, 30.0])
    num_dist = NumericDistribution(
        min=10.0,
        max=30.0,
        mean=20.0,
        std=10.0,
        zeros_count=0,
        negatives_count=0,
    )
    col_profile = ColumnProfile(
        name="test_col",
        physical_dtype="float64",
        inferred_type="numeric",
        row_count=3,
        missingness=MissingnessDetail(missing_count=0, missing_percentage=0.0),
        numeric=num_dist,
    )

    # False positive candidates that contain "li" or "ig" as substrings
    false_positives = [
        "client_status",
        "baseline_volume",
        "delivery_count",
        "flight_index",
        "unlimited_tier",
    ]
    for col in false_positives:
        res = infer_channel_column(col, dummy_series, col_profile)
        assert res is None, f"Expected '{col}' NOT to be inferred as media channel, but got {res}"

    # True positive candidates that should be recognized
    true_positives = [
        ("linkedin_spend", SemanticRole.MEDIA_CHANNEL),
        ("li_spend", SemanticRole.MEDIA_CHANNEL),
        ("meta_spend", SemanticRole.MEDIA_CHANNEL),
        ("tiktok_cost", SemanticRole.MEDIA_CHANNEL),
        ("snapchat_impressions", SemanticRole.METRIC_IMPRESSION),
        ("x_spend", SemanticRole.MEDIA_CHANNEL),
    ]
    for col, expected_role in true_positives:
        res = infer_channel_column(col, dummy_series, col_profile)
        assert res is not None, f"Expected '{col}' to be recognized as channel"
        assert res.role == expected_role, f"Expected role {expected_role} for '{col}', got {res.role}"


def test_mapping_profiles_storage_and_tenant_scoping(tmp_path):
    """Verify migration 007 and tenant-scoped CRUD for OrganizationMappingProfile."""
    db_path = tmp_path / "metadata.db"
    store = SQLiteMetadataStore(db_path)

    # Migration runner should advance to version 7
    runner = MigrationRunner(store.conn)
    assert runner.current_version() >= 7

    profile_alpha = {
        "profile_id": "prof_123",
        "organization_id": "tenant_alpha",
        "profile_name": "q4_campaign_alias",
        "mappings": {"ch_alpha": "meta_spend", "kpi_raw": "revenue"},
    }

    # Store profile for tenant_alpha
    store.put_mapping_profile(profile_alpha, tenant_id="tenant_alpha")

    # Fetch for tenant_alpha succeeds
    retrieved = store.get_mapping_profile("prof_123", tenant_id="tenant_alpha")
    assert retrieved is not None
    assert retrieved["profile_name"] == "q4_campaign_alias"
    assert retrieved["mappings"]["ch_alpha"] == "meta_spend"

    # Fetch for tenant_beta fails (strict multi-tenant isolation)
    isolated = store.get_mapping_profile("prof_123", tenant_id="tenant_beta")
    assert isolated is None

    # List mapping profiles is tenant-scoped
    alpha_list = store.list_mapping_profiles(tenant_id="tenant_alpha")
    assert len(alpha_list) == 1
    beta_list = store.list_mapping_profiles(tenant_id="tenant_beta")
    assert len(beta_list) == 0
