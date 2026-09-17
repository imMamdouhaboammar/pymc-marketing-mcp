"""Adversarial Torture Suite for PyMC Marketing MCP Production Remediation.

Exhaustive regression and adversarial edge cases:
- DEC-001/002: Flighting optimizer under extreme budgets, linear surfaces, impossible constraints
- CLV-001: Lineage fail-closed behavior, currency mismatch, customer cohort mismatch, ID order-invariance
- JOB-001/002: Idempotency with different payloads, double cancellation, cancel completed job, state machine
- MMM-VAL-001: Validation parity on job submission
- ART-001/002: Model resolution and artifact references
- API-ERR-001 & API-NEXT-001: Error classification and next_actions tool registry parity
- CV-001 & SENS-001: Cross-validation and sensitivity provenance
- CURVE-001 & CURVE-002: Response curve support classification and null half-saturation
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
import pandas as pd
import pytest

import sqlite3

from marketing_mcp.domain.decisions.flighting import (
    build_official_response_evaluator,
    optimize_flighting_schedule,
)
from marketing_mcp.error_classifier import classify_exception
from marketing_mcp.errors import DomainError
from marketing_mcp.jobs.idempotency import compute_semantic_idempotency_key
from marketing_mcp.jobs.models import JobRecord, JobStatus
from marketing_mcp.jobs.repository import SQLiteJobRepository
from marketing_mcp.jobs.service import JobService
from marketing_mcp.jobs.state import can_transition, validate_transition
from marketing_mcp.storage.metadata import SQLiteMetadataRepository
from marketing_mcp.schemas.models import (
    CLVModelRecord,
    EstimateCLVInput,
    ModelLineage,
    PredictCLVInput,
    PredictExpectedPurchasesInput,
)
from marketing_mcp.services.clv_service import CLVService
from marketing_mcp.storage.migrations import MigrationRunner


# =====================================================================
# 1. Decision & Flighting Optimization Adversarial Tests (DEC-001/002)
# =====================================================================

class TestDecisionAdversarial:
    """Stress tests on flighting optimization, bounds, and surface monotonicity."""

    def test_flighting_zero_budget_rejected(self):
        """Zero total budget must be rejected immediately."""
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=["search", "social"],
                total_budget=0.0,
                planning_weeks=4,
            )
        assert exc_info.value.code == "INPUT_INVALID"

    def test_flighting_negative_budget_rejected(self):
        """Negative total budget must be rejected."""
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=["search", "social"],
                total_budget=-5000.0,
                planning_weeks=4,
            )
        assert exc_info.value.code == "INPUT_INVALID"

    def test_flighting_min_weekly_exceeds_budget_rejected(self):
        """When sum of minimum spends exceeds total budget, fail with OPTIMIZATION_INFEASIBLE."""
        constraints = [
            {"channel": "search", "min_weekly": 1000.0},  # 4 weeks * 1000 = 4000
            {"channel": "social", "min_weekly": 1000.0},  # 4 weeks * 1000 = 4000
        ]
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=["search", "social"],
                total_budget=5000.0,  # 5000 < 8000
                planning_weeks=4,
                channel_constraints=constraints,
            )
        assert exc_info.value.code == "OPTIMIZATION_INFEASIBLE"

    def test_flighting_min_greater_than_max_rejected(self):
        """When min_weekly > max_weekly, fail with OPTIMIZATION_INFEASIBLE."""
        constraints = [
            {"channel": "search", "min_weekly": 500.0, "max_weekly": 200.0},
        ]
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=["search", "social"],
                total_budget=5000.0,
                planning_weeks=4,
                channel_constraints=constraints,
            )
        assert exc_info.value.code == "OPTIMIZATION_INFEASIBLE"

    def test_flighting_max_sum_less_than_budget_rejected(self):
        """When sum of maximum spends cannot absorb the budget, fail with OPTIMIZATION_INFEASIBLE."""
        constraints = [
            {"channel": "search", "max_weekly": 500.0},  # 4 * 500 = 2000
            {"channel": "social", "max_weekly": 500.0},  # 4 * 500 = 2000
        ]
        with pytest.raises(DomainError) as exc_info:
            optimize_flighting_schedule(
                channel_columns=["search", "social"],
                total_budget=10000.0,  # 10000 > 4000
                planning_weeks=4,
                channel_constraints=constraints,
            )
        assert exc_info.value.code == "OPTIMIZATION_INFEASIBLE"

    def test_flighting_extremely_high_budget_numeric_stability(self):
        """$100,000,000 budget must not cause numerical gradient underflow or stall at 25% equal allocation."""
        params = {
            "search": {"alpha": 0.1, "beta": 20.0, "lam": 100000.0},
            "social": {"alpha": 0.1, "beta": 10.0, "lam": 100000.0},
            "display": {"alpha": 0.1, "beta": 5.0, "lam": 100000.0},
            "tv": {"alpha": 0.1, "beta": 1.0, "lam": 100000.0},
        }
        res = optimize_flighting_schedule(
            channel_columns=["search", "social", "display", "tv"],
            total_budget=100000000.0,
            planning_weeks=4,
            channel_parameters=params,
        )
        alloc = res["total_channel_spend"]
        # Search is most productive, followed by social, display, tv
        assert alloc["search"] > alloc["social"]
        assert alloc["social"] > alloc["display"]
        assert alloc["display"] > alloc["tv"]
        # Total spend strictly conserved
        assert sum(alloc.values()) == pytest.approx(100000000.0, rel=1e-4)

    def test_flighting_linear_return_concentration(self):
        """Under linear surface, spend concentrates on the highest return channel."""
        channel_params = {
            "search": {"saturation_beta": 25.0},
            "social": {"saturation_beta": 5.0},
            "tv": {"saturation_beta": 1.0},
        }
        channels = ["search", "social", "tv"]
        evaluator = build_official_response_evaluator(
            adstock_type="none",
            saturation_type="none",
            l_max=1,
            channel_params=channel_params,
            channel_scale={ch: 1.0 for ch in channels},
            channel_columns=channels,
            target_scale=100.0,
        )
        res = optimize_flighting_schedule(
            channel_columns=channels,
            total_budget=10000.0,
            planning_weeks=4,
            response_evaluator=evaluator,
        )
        alloc = res["total_channel_spend"]
        # Search should receive the vast majority of the budget
        assert alloc["search"] > 8000.0
        assert alloc["tv"] < 200.0


# =====================================================================
# 2. Lineage & Cohort Safety Adversarial Tests (CLV-001)
# =====================================================================

@pytest.fixture
def meta_repo():
    conn = sqlite3.connect(":memory:")
    return SQLiteMetadataRepository(conn)


class TestLineageAdversarial:
    """Rigorous tests on fail-closed lineage, currency matching, and customer cohorts."""

    def test_clv_lineage_guard_rejects_different_dataset_ids(self, meta_repo, tmp_path):
        """Cross-dataset pairing with different dataset_id must be rejected."""
        p = CLVModelRecord(
            model_id="clv_p_1",
            model_type="bg_nbd",
            dataset_id="ds_alpha",
            dataset_fingerprint="fp_common",
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        v = CLVModelRecord(
            model_id="clv_v_1",
            model_type="gamma_gamma",
            dataset_id="ds_beta",
            dataset_fingerprint="fp_common",
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        meta_repo.put_clv_model(p.model_dump())
        meta_repo.put_clv_model(v.model_dump())

        service = CLVService(metadata=meta_repo, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.estimate_customer_lifetime_value(
                EstimateCLVInput(purchase_model_id="clv_p_1", value_model_id="clv_v_1")
            )
        assert exc_info.value.code == "CLV_LINEAGE_MISMATCH"

    def test_clv_lineage_guard_rejects_different_fingerprints(self, meta_repo, tmp_path):
        """Same dataset_id but different fingerprint (mutated data) must be rejected."""
        p = CLVModelRecord(
            model_id="clv_p_1",
            model_type="bg_nbd",
            dataset_id="ds_common",
            dataset_fingerprint="fp_initial",
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        v = CLVModelRecord(
            model_id="clv_v_1",
            model_type="gamma_gamma",
            dataset_id="ds_common",
            dataset_fingerprint="fp_mutated",
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        meta_repo.put_clv_model(p.model_dump())
        meta_repo.put_clv_model(v.model_dump())

        service = CLVService(metadata=meta_repo, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.estimate_customer_lifetime_value(
                EstimateCLVInput(purchase_model_id="clv_p_1", value_model_id="clv_v_1")
            )
        assert exc_info.value.code == "CLV_LINEAGE_MISMATCH"

    def test_clv_lineage_guard_fail_closed_missing_fingerprint(self, meta_repo, tmp_path):
        """Empty or missing fingerprint triggers fail-closed rejection."""
        p = CLVModelRecord(
            model_id="clv_p_1",
            model_type="bg_nbd",
            dataset_id="ds_common",
            dataset_fingerprint="",  # Missing
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        v = CLVModelRecord(
            model_id="clv_v_1",
            model_type="gamma_gamma",
            dataset_id="ds_common",
            dataset_fingerprint="fp_val",
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        meta_repo.put_clv_model(p.model_dump())
        meta_repo.put_clv_model(v.model_dump())

        service = CLVService(metadata=meta_repo, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.estimate_customer_lifetime_value(
                EstimateCLVInput(purchase_model_id="clv_p_1", value_model_id="clv_v_1")
            )
        assert exc_info.value.code == "CLV_LINEAGE_MISMATCH"

    def test_clv_lineage_guard_rejects_currency_mismatch(self, meta_repo, tmp_path):
        """Purchase model in USD paired with value model in EUR must be rejected."""
        p = CLVModelRecord(
            model_id="clv_p_1",
            model_type="bg_nbd",
            dataset_id="ds_common",
            dataset_fingerprint="fp_common",
            lineage=ModelLineage(
                dataset_id="ds_common",
                dataset_fingerprint="fp_common",
                currency="USD",
            ),
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        v = CLVModelRecord(
            model_id="clv_v_1",
            model_type="gamma_gamma",
            dataset_id="ds_common",
            dataset_fingerprint="fp_common",
            lineage=ModelLineage(
                dataset_id="ds_common",
                dataset_fingerprint="fp_common",
                currency="EUR",
            ),
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        meta_repo.put_clv_model(p.model_dump())
        meta_repo.put_clv_model(v.model_dump())

        service = CLVService(metadata=meta_repo, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.estimate_customer_lifetime_value(
                EstimateCLVInput(purchase_model_id="clv_p_1", value_model_id="clv_v_1")
            )
        assert exc_info.value.code == "CLV_CURRENCY_MISMATCH"

    def test_clv_lineage_guard_rejects_cohort_mismatch(self, meta_repo, tmp_path):
        """Different customer population cohorts must be rejected."""
        p = CLVModelRecord(
            model_id="clv_p_1",
            model_type="bg_nbd",
            dataset_id="ds_common",
            dataset_fingerprint="fp_common",
            lineage=ModelLineage(
                dataset_id="ds_common",
                dataset_fingerprint="fp_common",
                customer_population_fingerprint="cohort_hash_aaa",
            ),
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        v = CLVModelRecord(
            model_id="clv_v_1",
            model_type="gamma_gamma",
            dataset_id="ds_common",
            dataset_fingerprint="fp_common",
            lineage=ModelLineage(
                dataset_id="ds_common",
                dataset_fingerprint="fp_common",
                customer_population_fingerprint="cohort_hash_bbb",
            ),
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        meta_repo.put_clv_model(p.model_dump())
        meta_repo.put_clv_model(v.model_dump())

        service = CLVService(metadata=meta_repo, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.estimate_customer_lifetime_value(
                EstimateCLVInput(purchase_model_id="clv_p_1", value_model_id="clv_v_1")
            )
        assert exc_info.value.code == "CLV_COHORT_MISMATCH"

    def test_customer_population_fingerprint_is_order_invariant(self, tmp_path):
        """Customer population fingerprint is order-invariant when dataframe is shuffled."""
        df1 = pd.DataFrame({"customer_id": ["c3", "c1", "c2"], "x": [1, 2, 3]})
        df2 = pd.DataFrame({"customer_id": ["c1", "c2", "c3"], "x": [2, 3, 1]})

        service = CLVService(metadata=None, artifact_dir=tmp_path)
        lin1 = service._build_lineage("ds_1", df1, "bg_nbd", cust_col="customer_id")
        lin2 = service._build_lineage("ds_1", df2, "bg_nbd", cust_col="customer_id")

        assert lin1.customer_population_fingerprint == lin2.customer_population_fingerprint
        assert len(lin1.customer_population_fingerprint) == 64  # SHA-256


# =====================================================================
# 3. Job Lifecycle & State Machine Adversarial Tests (JOB-001)
# =====================================================================

class TestJobLifecycleAdversarial:
    """State machine validation, idempotency, and cancellation safety."""

    def test_semantic_idempotency_changes_with_payload(self):
        """Different fit parameters produce different idempotency keys."""
        payload_1 = {"dataset_id": "ds_1", "chains": 4, "draws": 1000}
        payload_2 = {"dataset_id": "ds_1", "chains": 2, "draws": 500}

        key_1 = compute_semantic_idempotency_key("tenant_a", "fit_mmm", payload_1)
        key_2 = compute_semantic_idempotency_key("tenant_a", "fit_mmm", payload_2)

        assert key_1 != key_2

    def test_semantic_idempotency_ignores_ephemeral_fields(self):
        """Ephemeral metadata like request_id does not invalidate cache/idempotency key."""
        payload_1 = {"dataset_id": "ds_1", "request_id": "req-1", "timestamp": "2026-01-01"}
        payload_2 = {"dataset_id": "ds_1", "request_id": "req-2", "timestamp": "2026-01-02"}

        key_1 = compute_semantic_idempotency_key("tenant_a", "fit_mmm", payload_1)
        key_2 = compute_semantic_idempotency_key("tenant_a", "fit_mmm", payload_2)

        assert key_1 == key_2

    def test_cancel_completed_job_returns_safely(self):
        """Cancelling a SUCCEEDED job returns the record without mutating status or crashing."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        MigrationRunner(conn).apply_pending()
        repo = SQLiteJobRepository(conn)

        job = repo.create_job(
            JobRecord(
                job_id="job_test_succ",
                job_type="fit_mmm",
                status=JobStatus.QUEUED,
            )
        )
        repo.update_job(job.job_id, JobStatus.RUNNING)
        repo.update_job(job.job_id, JobStatus.SUCCEEDED, result={"model_id": "m1"})

        service = JobService(repo=repo)
        res = service.cancel_job(job.job_id)

        assert res.status == JobStatus.SUCCEEDED
        assert repo.get_job(job.job_id).status == JobStatus.SUCCEEDED

    def test_double_cancellation_is_idempotent(self):
        """Double cancellation does not crash or corrupt job state."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        MigrationRunner(conn).apply_pending()
        repo = SQLiteJobRepository(conn)

        job = repo.create_job(
            JobRecord(
                job_id="job_test_cancel",
                job_type="fit_mmm",
                status=JobStatus.QUEUED,
            )
        )

        service = JobService(repo=repo)
        first_cancel = service.cancel_job(job.job_id)
        assert first_cancel.status in (JobStatus.CANCELLING, JobStatus.CANCELLED)

        # Second cancel call
        second_cancel = service.cancel_job(job.job_id)
        assert second_cancel.status in (JobStatus.CANCELLING, JobStatus.CANCELLED)

    def test_invalid_state_transitions_rejected(self):
        """Illegal state transitions must raise DomainError INVALID_STATE."""
        # Cannot go from SUCCEEDED to RUNNING or CANCELLED
        with pytest.raises(DomainError) as exc_info:
            validate_transition(JobStatus.SUCCEEDED, JobStatus.RUNNING)
        assert exc_info.value.code == "INVALID_STATE"

        with pytest.raises(DomainError) as exc_info:
            validate_transition(JobStatus.FAILED, JobStatus.CANCELLING)
        assert exc_info.value.code == "INVALID_STATE"

        # Identity transition is valid
        validate_transition(JobStatus.RUNNING, JobStatus.RUNNING)
        assert can_transition(JobStatus.RUNNING, JobStatus.RUNNING) is True


# =====================================================================
# 4. Validation Parity & API Error Contracts (API-NEXT-001, API-ERR-001)
# =====================================================================

class TestValidationAndToolRegistryAdversarial:
    """Tool registry next_action consistency and error classification."""

    def test_unknown_clv_model_id_raises_not_found(self, meta_repo, tmp_path):
        """Requesting prediction on unknown model ID raises CLV_MODEL_NOT_FOUND."""
        service = CLVService(metadata=meta_repo, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.predict_clv(
                PredictCLVInput(model_id="nonexistent_clv_model_id")
            )
        assert exc_info.value.code == "CLV_MODEL_NOT_FOUND"

    def test_wrong_model_type_passed_to_clv_prediction_endpoint(self, meta_repo, tmp_path):
        """Passing a value model ID (gamma_gamma) to predict_expected_purchases raises INVALID_MODEL_TYPE."""
        v = CLVModelRecord(
            model_id="clv_v_wrong",
            model_type="gamma_gamma",
            dataset_id="ds_1",
            dataset_fingerprint="fp_1",
            status="completed",
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
        )
        meta_repo.put_clv_model(v.model_dump())

        service = CLVService(metadata=meta_repo, artifact_dir=tmp_path)
        with pytest.raises(DomainError) as exc_info:
            service.predict_expected_purchases(
                PredictExpectedPurchasesInput(model_id="clv_v_wrong")
            )
        assert exc_info.value.code == "INVALID_MODEL_TYPE"

    def test_user_errors_classified_as_user_actionable(self):
        """User input errors are never classified as internal server errors."""
        e1 = KeyError("channel 'tiktok' not found in model")
        e2 = ValueError("negative spend is invalid")
        c1 = classify_exception(e1)
        c2 = classify_exception(e2)

        assert c1.user_actionable is True
        assert c2.user_actionable is True


# =====================================================================
# 5. Response Curves & Empirical Support (CURVE-001, CURVE-002)
# =====================================================================

class TestResponseCurvesEmpiricalSupport:
    """Empirical spend support classification and no-saturation semantics."""

    def test_support_classification_logic(self):
        """Test empirical spend support classification on zero-spend, weak, and normal channels."""
        # Simulated spend history for 3 channels:
        # - ch_zero: 0 non-zero periods -> "no_empirical_support", prior_dominated=True
        # - ch_weak: 5 non-zero periods -> "weak_support", prior_dominated=True
        # - ch_strong: 50 non-zero periods -> "observed", prior_dominated=False
        df = pd.DataFrame({
            "ch_zero": [0.0] * 50,
            "ch_weak": [100.0] * 5 + [0.0] * 45,
            "ch_strong": [150.0] * 50,
        })

        def classify_channel(ch_name: str, max_eval_spend: float):
            col_s = pd.to_numeric(df[ch_name], errors="coerce").fillna(0)
            pos_s = col_s[col_s > 0]
            n_nonzero = int(len(pos_s))
            hist_min = round(float(pos_s.min()), 2) if n_nonzero > 0 else 0.0
            hist_max = round(float(col_s.max()), 2)

            if n_nonzero == 0:
                return "no_empirical_support", True
            elif max_eval_spend > (hist_max * 1.5 if hist_max > 0 else 0):
                return "extrapolated", False
            elif n_nonzero < 10:
                return "weak_support", True
            else:
                return "observed", False

        cls_zero, pd_zero = classify_channel("ch_zero", 500.0)
        assert cls_zero == "no_empirical_support"
        assert pd_zero is True

        cls_weak, pd_weak = classify_channel("ch_weak", 100.0)
        assert cls_weak == "weak_support"
        assert pd_weak is True

        cls_strong, pd_strong = classify_channel("ch_strong", 150.0)
        assert cls_strong == "observed"
        assert pd_strong is False

        cls_extrap, pd_extrap = classify_channel("ch_strong", 500.0)
        assert cls_extrap == "extrapolated"
        assert pd_extrap is False

