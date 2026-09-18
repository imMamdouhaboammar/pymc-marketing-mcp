"""Unit tests for Experiment Evidence Registry and calibration resolution (T5).

Fast tests — zero sampling required.
Coverage:
- Registration and retrieval of experiment evidence records
- Tenant isolation across multiple tenants
- Immutability enforcement (preventing parameter modification of existing records)
- Resolution into LiftTestMeasurement for calibration
- Archived experiments blocked from calibration
"""

from __future__ import annotations

import pytest

from marketing_mcp.domain.experiments import (
    ExperimentRegistryService,
    RegisterExperimentInput,
)
from marketing_mcp.errors import DomainError
from marketing_mcp.storage.metadata import SQLiteMetadataStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "metadata.db"
    s = SQLiteMetadataStore(db_path)
    yield s
    s.close()


@pytest.fixture
def service(store):
    return ExperimentRegistryService(store)


class TestExperimentRegistry:
    def test_register_and_get_experiment(self, service):
        input_data = RegisterExperimentInput(
            experiment_id="exp_meta_01",
            channel="meta_spend",
            geo="US",
            methodology="geo_lift",
            start_date="2025-01-01",
            end_date="2025-01-28",
            treatment_description="Holdout test with 20% geo holdout",
            baseline_spend=50000.0,
            spend_delta=10000.0,
            measured_incremental_response=25000.0,
            standard_error=2500.0,
            evidence_quality_score=0.90,
            source="in_house_incrementality_platform",
        )
        rec = service.register(input_data)
        assert rec.experiment_id == "exp_meta_01"
        assert rec.channel == "meta_spend"
        assert rec.measured_incremental_response == 25000.0
        assert rec.archived is False

        fetched = service.get("exp_meta_01")
        assert fetched.experiment_id == "exp_meta_01"
        assert fetched.evidence_quality_score == 0.90
        assert "registered_at" in fetched.provenance

    def test_tenant_isolation(self, service):
        # Register in tenant A
        exp_a = RegisterExperimentInput(
            experiment_id="exp_tenant_a",
            channel="search_spend",
            start_date="2025-01-01",
            end_date="2025-01-30",
            baseline_spend=1000.0,
            spend_delta=500.0,
            measured_incremental_response=1200.0,
            standard_error=100.0,
            tenant_id="tenant_alpha",
        )
        service.register(exp_a, tenant_id="tenant_alpha")

        # Tenant A can access
        assert service.get("exp_tenant_a", tenant_id="tenant_alpha").channel == "search_spend"

        # Tenant B cannot access Tenant A's experiment
        with pytest.raises(DomainError) as exc_info:
            service.get("exp_tenant_a", tenant_id="tenant_beta")
        assert exc_info.value.code == "EXPERIMENT_NOT_FOUND"

        # List filtered by tenant
        list_a = service.list_all(tenant_id="tenant_alpha")
        list_b = service.list_all(tenant_id="tenant_beta")
        assert len(list_a) == 1
        assert len(list_b) == 0

    def test_immutability_enforcement(self, service):
        """Historic experiment evidence cannot be silently modified."""
        input_data = RegisterExperimentInput(
            experiment_id="exp_immutable",
            channel="tv_spend",
            start_date="2025-01-01",
            end_date="2025-01-15",
            baseline_spend=10000.0,
            spend_delta=5000.0,
            measured_incremental_response=8000.0,
            standard_error=1000.0,
        )
        service.register(input_data)

        # Attempt to modify measured_incremental_response under same experiment_id
        tampered = RegisterExperimentInput(
            experiment_id="exp_immutable",
            channel="tv_spend",
            start_date="2025-01-01",
            end_date="2025-01-15",
            baseline_spend=10000.0,
            spend_delta=5000.0,
            measured_incremental_response=15000.0,  # tampered value
            standard_error=1000.0,
        )
        with pytest.raises(DomainError) as exc_info:
            service.register(tampered)
        assert exc_info.value.code == "IMMUTABLE_EVIDENCE_VIOLATION"

    def test_resolve_for_calibration_parity(self, service):
        """Registry records convert to LiftTestMeasurement with exact parameter parity."""
        input_data = RegisterExperimentInput(
            experiment_id="exp_calib_01",
            channel="meta_spend",
            geo="US",
            start_date="2025-02-01",
            end_date="2025-02-28",
            baseline_spend=20000.0,
            spend_delta=5000.0,
            measured_incremental_response=12500.0,
            standard_error=1500.0,
        )
        service.register(input_data)

        tests = service.resolve_for_calibration(["exp_calib_01"])
        assert len(tests) == 1
        m = tests[0]
        assert m.channel == "meta_spend"
        assert m.geo == "US"
        assert m.x == 20000.0
        assert m.delta_x == 5000.0
        assert m.delta_y == 12500.0
        assert m.sigma == 1500.0
        assert "ExperimentRegistry:exp_calib_01" in m.description

    def test_archived_experiment_blocked_from_calibration(self, service):
        input_data = RegisterExperimentInput(
            experiment_id="exp_to_archive",
            channel="display_spend",
            start_date="2024-01-01",
            end_date="2024-01-30",
            baseline_spend=5000.0,
            spend_delta=2000.0,
            measured_incremental_response=1000.0,
            standard_error=800.0,
        )
        service.register(input_data)
        service.archive("exp_to_archive")

        # Marked as archived in listing
        active = service.list_all(include_archived=False)
        all_exp = service.list_all(include_archived=True)
        assert len(active) == 0
        assert len(all_exp) == 1

        # Blocked from calibration
        with pytest.raises(DomainError) as exc_info:
            service.resolve_for_calibration(["exp_to_archive"])
        assert exc_info.value.code == "EXPERIMENT_ARCHIVED"
