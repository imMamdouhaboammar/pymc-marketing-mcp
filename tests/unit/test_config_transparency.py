"""Unit tests for configuration transparency and audit attribution (T6).

Fast tests — zero sampling required.
Coverage:
- Round-trip fidelity of requested_config
- Categorization into user_specified, default_applied, intelligence_inferred
- effective_config reconstruction completeness
"""

from __future__ import annotations

from marketing_mcp.domain.configuration import build_config_audit
from marketing_mcp.schemas.models import FitMMMInput, ModelRecord


class TestConfigTransparency:
    def test_build_config_audit_attributes_sources_correctly(self):
        requested = {
            "target_column": "revenue",
            "channel_columns": ["meta_spend", "search_spend"],
        }
        resolved = {
            "target_column": "revenue",
            "channel_columns": ["meta_spend", "search_spend"],
            "yearly_seasonality": None,
            "sampler": {"draws": 1000, "chains": 4},
        }
        effective = {
            "target_column": "revenue",
            "channel_columns": ["meta_spend", "search_spend"],
            "yearly_seasonality": None,
            "sampler": {"draws": 1000, "chains": 4},
            "channel_scale": {"meta_spend": 1200.0, "search_spend": 950.0},
        }

        audit = build_config_audit(requested, resolved, effective)
        attrs = audit["attributes"]

        # Explicitly requested
        assert attrs["target_column"]["attribution"] == "user_specified"
        assert attrs["channel_columns"]["attribution"] == "user_specified"

        # Defaults added during schema resolution
        assert attrs["yearly_seasonality"]["attribution"] == "default_applied"
        assert attrs["sampler"]["attribution"] == "default_applied"

        # Runtime calibrated
        assert attrs["channel_scale"]["attribution"] == "runtime_calibrated"

        summary = audit["summary"]
        assert summary["user_specified_count"] == 2
        assert summary["default_applied_count"] == 2
        assert summary["runtime_calibrated_count"] == 1

    def test_model_record_preserves_distinct_configs(self):
        req = {"target_column": "sales"}
        res = {"target_column": "sales", "sampler": {"draws": 500}}
        eff = {"target_column": "sales", "sampler": {"draws": 500}, "channel_scale": 1.0}
        audit = build_config_audit(req, res, eff)

        rec = ModelRecord(
            model_id="test_m1",
            dataset_id="ds_1",
            config=res,
            requested_config=req,
            resolved_config=res,
            effective_config=eff,
            config_diff=audit,
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )

        assert rec.requested_config == req
        assert rec.resolved_config == res
        assert rec.effective_config == eff
        assert rec.config_diff["summary"]["user_specified_count"] == 1

    def test_fit_mmm_input_exclude_unset_captures_raw_user_intent(self):
        fit_input = FitMMMInput(
            dataset_id="ds_raw",
            date_column="date",
            target_column="conversions",
            channel_columns=["tv"],
        )
        raw_intent = fit_input.model_dump(exclude_unset=True)
        # Only explicitly passed fields are in raw_intent
        assert set(raw_intent.keys()) == {"dataset_id", "date_column", "target_column", "channel_columns"}

        resolved = fit_input.model_dump()
        # Resolved contains all schema defaults (sampler, adstock, saturation, etc.)
        assert "sampler" in resolved
        assert "adstock" in resolved
        assert "saturation" in resolved

        audit = build_config_audit(raw_intent, resolved)
        assert audit["attributes"]["target_column"]["attribution"] == "user_specified"
        assert audit["attributes"]["sampler"]["attribution"] == "default_applied"
