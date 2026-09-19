"""Contract tests for user_overrides typed schema and normalization (P1 regression)."""

from __future__ import annotations

import asyncio
import json

import pandas as pd
import pytest

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.errors import DomainError
from marketing_mcp.intelligence.contracts.semantics import SemanticRole
from marketing_mcp.mcp.server import create_server
from marketing_mcp.schemas.overrides import UserOverridesInput, normalize_user_overrides
from marketing_mcp.security.principal import Principal


class TestUserOverridesNormalization:
    def test_canonical_business_shorthand_normalization(self):
        overrides = {
            "target_column": "revenue_usd",
            "channel_columns": ["tv_spend", "radio_spend"],
            "control_columns": ["holiday_index"],
            "dims": ["country"],
        }
        normalized = normalize_user_overrides(overrides)
        assert normalized["revenue_usd"]["role"] == SemanticRole.TARGET
        assert normalized["tv_spend"]["role"] == SemanticRole.MEDIA_CHANNEL
        assert normalized["radio_spend"]["role"] == SemanticRole.MEDIA_CHANNEL
        assert normalized["holiday_index"]["role"] == SemanticRole.CONTROL
        assert normalized["country"]["role"] == SemanticRole.DIMENSION

    def test_typed_model_normalization(self):
        model = UserOverridesInput(
            target_column="sales",
            channels=["meta", "google"],
            date_column="week_start",
        )
        normalized = normalize_user_overrides(model)
        assert normalized["sales"]["role"] == SemanticRole.TARGET
        assert normalized["meta"]["role"] == SemanticRole.MEDIA_CHANNEL
        assert normalized["google"]["role"] == SemanticRole.MEDIA_CHANNEL
        assert normalized["week_start"]["role"] == SemanticRole.DATE

    def test_backward_compatible_column_keyed_dict(self):
        # Dict with {"role": SemanticRole...}
        overrides = {
            "crm_revenue": {"role": SemanticRole.TARGET},
            "fb_ads": {"role": "media_channel"},
            "print_ads": "media_channel",
        }
        normalized = normalize_user_overrides(overrides)
        assert normalized["crm_revenue"]["role"] == SemanticRole.TARGET
        assert normalized["fb_ads"]["role"] == SemanticRole.MEDIA_CHANNEL
        assert normalized["print_ads"]["role"] == SemanticRole.MEDIA_CHANNEL

    def test_empty_or_none_overrides(self):
        assert normalize_user_overrides(None) == {}
        assert normalize_user_overrides({}) == {}

    def test_invalid_shapes_raise_input_invalid(self):
        # target_column as list
        with pytest.raises(DomainError) as exc1:
            normalize_user_overrides({"target_column": ["rev1", "rev2"]})
        assert exc1.value.code == "INPUT_INVALID"

        # malformed roles
        with pytest.raises(DomainError) as exc2:
            normalize_user_overrides({"roles": "not_a_dict"})
        assert exc2.value.code == "INPUT_INVALID"

        # completely invalid top-level type
        with pytest.raises(DomainError) as exc3:
            normalize_user_overrides("invalid_string_instead_of_dict")
        assert exc3.value.code == "INPUT_INVALID"


class TestMCPToolsWithUserOverrides:
    @pytest.fixture
    def test_env(self, tmp_path):
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
            tenant_id="tenant_overrides",
            scopes=frozenset({"marketing:read", "marketing:model"}),
            auth_type="api_key",
        )
        server = create_server(app, context_provider=lambda: type("Context", (), {"principal": principal})())

        # Register a simple test dataset
        df = pd.DataFrame({
            "date": pd.date_range("2026-01-01", periods=60, freq="D").strftime("%Y-%m-%d"),
            "revenue_usd": [100.0 + i for i in range(60)],
            "ad_spend": [10.0 + (i % 5) * 5 for i in range(60)],
        })
        reg = app.datasets.register_bytes(
            df.to_csv(index=False).encode("utf-8"),
            format="csv",
            filename="overrides_test.csv",
            principal=principal,
        )
        return app, server, reg.dataset_id

    def _call(self, server, tool: str, args: dict) -> dict:
        res = asyncio.run(server.call_tool(tool, args))
        item = res[0] if isinstance(res, list) else getattr(res, "content", [None])[0]
        text = getattr(item, "text", None) or str(item)
        return json.loads(text)

    def test_inspect_dataset_with_business_shorthand_overrides(self, test_env):
        app, server, dataset_id = test_env
        # Exact real-user payload that previously failed with AttributeError: 'str' object has no attribute 'get'
        payload = {
            "dataset_id": dataset_id,
            "user_overrides": {"target_column": "revenue_usd"},
        }
        resp = self._call(server, "inspect_dataset", payload)
        assert "summary" in resp
        assert "revenue_usd" in resp["summary"]["possible_targets"]

    def test_validate_dataset_with_business_shorthand_overrides(self, test_env):
        app, server, dataset_id = test_env
        payload = {
            "dataset_id": dataset_id,
            "date_column": "date",
            "target_column": "revenue_usd",
            "channel_columns": ["ad_spend"],
            "user_overrides": {"target_column": "revenue_usd"},
        }
        resp = self._call(server, "validate_dataset", payload)
        assert "summary" in resp
        assert resp["summary"]["valid_for_modeling"] is True
