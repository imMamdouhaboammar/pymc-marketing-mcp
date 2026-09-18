"""Canonical Error Normalization and Diagnostic Error Architecture for PyMC Marketing MCP."""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def generate_error_id() -> str:
    """Generate a high-entropy, time-ordered, opaque error identifier."""
    # Prefix with err_, followed by hex milliseconds and random entropy
    ms_hex = f"{int(time.time() * 1000):012x}"
    entropy = secrets.token_hex(6)
    return f"err_{ms_hex}{entropy}"


class ErrorCategory(str, Enum):
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    INPUT = "INPUT"
    DATASET = "DATASET"
    VALIDATION = "VALIDATION"
    MODELING = "MODELING"
    DIAGNOSTICS = "DIAGNOSTICS"
    STATISTICAL = "STATISTICAL"
    OPTIMIZATION = "OPTIMIZATION"
    CALIBRATION = "CALIBRATION"
    MODEL_SELECTION = "MODEL_SELECTION"
    CLV = "CLV"
    JOB = "JOB"
    PERSISTENCE = "PERSISTENCE"
    ARTIFACT = "ARTIFACT"
    NETWORK = "NETWORK"
    DEPENDENCY = "DEPENDENCY"
    CONFIGURATION = "CONFIGURATION"
    RESOURCE = "RESOURCE"
    TIMEOUT = "TIMEOUT"
    CANCELLATION = "CANCELLATION"
    INTERNAL = "INTERNAL"


class ErrorSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ErrorDefinition:
    """Contract definition for a machine-readable error code."""

    code: str
    category: ErrorCategory
    severity: ErrorSeverity = ErrorSeverity.ERROR
    retryable: bool = False
    http_status: int = 500
    user_actionable: bool = False
    suggested_action: str | None = None


# Canonical catalog of stable error codes
ERROR_CATALOG: dict[str, ErrorDefinition] = {
    # Authentication & Authorization
    "AUTH_REQUIRED": ErrorDefinition(
        code="AUTH_REQUIRED",
        category=ErrorCategory.AUTHENTICATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=401,
        user_actionable=True,
        suggested_action="Provide a valid Authorization Bearer token or X-API-Key header",
    ),
    "AUTH_FORBIDDEN": ErrorDefinition(
        code="AUTH_FORBIDDEN",
        category=ErrorCategory.AUTHORIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=403,
        user_actionable=True,
        suggested_action="Request required permission scopes or tenant access from administrator",
    ),
    "SSRF_DETECTED": ErrorDefinition(
        code="SSRF_DETECTED",
        category=ErrorCategory.AUTHORIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=403,
        user_actionable=True,
        suggested_action="Provide a publicly reachable HTTP/HTTPS URL",
    ),
    "DATASET_ACCESS_DENIED": ErrorDefinition(
        code="DATASET_ACCESS_DENIED",
        category=ErrorCategory.AUTHORIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=403,
        user_actionable=False,
        suggested_action="Ensure your tenant owns this dataset",
    ),

    # Input validation
    "INVALID_ARGUMENT": ErrorDefinition(
        code="INVALID_ARGUMENT",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Inspect input arguments and correct parameter values",
    ),
    "INPUT_INVALID": ErrorDefinition(
        code="INPUT_INVALID",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Inspect input arguments and correct parameter values",
    ),
    "MISSING_INPUT": ErrorDefinition(
        code="MISSING_INPUT",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Provide the required input parameters",
    ),
    "INVALID_IDENTIFIER": ErrorDefinition(
        code="INVALID_IDENTIFIER",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Provide a valid alphanumeric identifier",
    ),
    "INVALID_BASE64": ErrorDefinition(
        code="INVALID_BASE64",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Provide valid base64-encoded file bytes",
    ),
    "UNSUPPORTED_FORMAT": ErrorDefinition(
        code="UNSUPPORTED_FORMAT",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Provide file in a supported format",
    ),
    "UNSUPPORTED_SCHEME": ErrorDefinition(
        code="UNSUPPORTED_SCHEME",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Provide a valid http:// or https:// URL",
    ),
    "UNSUPPORTED_OPERATION": ErrorDefinition(
        code="UNSUPPORTED_OPERATION",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="This operation is not supported for the target model or dataset",
    ),
    "DATA_INVALID": ErrorDefinition(
        code="DATA_INVALID",
        category=ErrorCategory.INPUT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Inspect input data dimensions and structure",
    ),

    # Datasets
    "UNSUPPORTED_DATASET_FORMAT": ErrorDefinition(
        code="UNSUPPORTED_DATASET_FORMAT",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Provide dataset in CSV or Parquet format",
    ),
    "DATASET_NOT_FOUND": ErrorDefinition(
        code="DATASET_NOT_FOUND",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Register dataset before referencing it or verify dataset_id",
    ),
    "DATASET_PARSE_FAILED": ErrorDefinition(
        code="DATASET_PARSE_FAILED",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Ensure dataset is a valid, well-formed CSV or Parquet file",
    ),
    "DATASET_EMPTY": ErrorDefinition(
        code="DATASET_EMPTY",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Provide a non-empty dataset with at least one data row",
    ),
    "DATASET_TOO_LARGE": ErrorDefinition(
        code="DATASET_TOO_LARGE",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=413,
        user_actionable=True,
        suggested_action="Pre-aggregate or filter dataset to reduce size before registering",
    ),
    "REMOTE_DATASET_FETCH_FAILED": ErrorDefinition(
        code="REMOTE_DATASET_FETCH_FAILED",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=502,
        user_actionable=False,
        suggested_action="Verify remote server availability and network connectivity",
    ),
    "REMOTE_DATASET_TOO_LARGE": ErrorDefinition(
        code="REMOTE_DATASET_TOO_LARGE",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=413,
        user_actionable=True,
        suggested_action="Upload a smaller dataset or increase max_dataset_mb",
    ),
    "CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE": ErrorDefinition(
        code="CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Pass dataset as CSV text in 'content' or base64 in 'content_base64'",
    ),
    "FILE_NOT_FOUND": ErrorDefinition(
        code="FILE_NOT_FOUND",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Verify file path exists on the server",
    ),
    "DATASET_FILE_MISSING": ErrorDefinition(
        code="DATASET_FILE_MISSING",
        category=ErrorCategory.DATASET,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Verify dataset file exists",
    ),

    # Validation
    "DATASET_VALIDATION_FAILED": ErrorDefinition(
        code="DATASET_VALIDATION_FAILED",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Fix schema, date formatting, and missing required columns in dataset before fitting",
    ),
    "INVALID_DATASET": ErrorDefinition(
        code="INVALID_DATASET",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Fix schema, date formatting, and missing required columns in dataset",
    ),
    "MISSING_PERIODS": ErrorDefinition(
        code="MISSING_PERIODS",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Impute or provide observations for missing historical periods",
    ),
    "NON_RECTANGULAR_PANEL": ErrorDefinition(
        code="NON_RECTANGULAR_PANEL",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Ensure all dimension panels have equal observation dates",
    ),
    "MISSING_COLUMNS": ErrorDefinition(
        code="MISSING_COLUMNS",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Map existing dataset columns or provide the required target and media columns",
    ),

    # Modeling
    "MODEL_NOT_FOUND": ErrorDefinition(
        code="MODEL_NOT_FOUND",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Fit a model before referencing it or verify model_id",
    ),
    "MODEL_NOT_FITTED": ErrorDefinition(
        code="MODEL_NOT_FITTED",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=409,
        user_actionable=True,
        suggested_action="Wait for model fitting job to complete before accessing model",
    ),
    "MODEL_NOT_READY": ErrorDefinition(
        code="MODEL_NOT_READY",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=409,
        user_actionable=True,
        suggested_action="Wait for model fitting to finish before calibration",
    ),
    "MODEL_ARTIFACT_CORRUPTED": ErrorDefinition(
        code="MODEL_ARTIFACT_CORRUPTED",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.CRITICAL,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Refit model to generate a clean posterior artifact",
    ),
    "MODEL_DESERIALIZATION_FAILED": ErrorDefinition(
        code="MODEL_DESERIALIZATION_FAILED",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Verify NetCDF library compatibility and refit model",
    ),
    "MODEL_FIT_FAILED": ErrorDefinition(
        code="MODEL_FIT_FAILED",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Inspect sampling parameters, priors, and dataset dimensions",
    ),
    "MMM_FIT_FAILED": ErrorDefinition(
        code="MMM_FIT_FAILED",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Review model configuration and dataset distributions",
    ),
    "LONG_TERM_MULTIPLIER_UNDEFINED": ErrorDefinition(
        code="LONG_TERM_MULTIPLIER_UNDEFINED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action=(
            "Choose a target/channel with non-zero contemporaneous impact or inspect raw impulse responses"
        ),
    ),
    "LONG_TERM_UNCERTAINTY_REQUIRED": ErrorDefinition(
        code="LONG_TERM_UNCERTAINTY_REQUIRED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action=(
            "Use a Bayesian long-term-effects model with posterior uncertainty before decision rollup"
        ),
    ),
    "LONG_TERM_GATE_REJECTED": ErrorDefinition(
        code="LONG_TERM_GATE_REJECTED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Review time-series stability before using long-term effects in decisions",
    ),
    "ANALYSIS_UNAVAILABLE": ErrorDefinition(
        code="ANALYSIS_UNAVAILABLE",
        category=ErrorCategory.MODELING,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=409,
        user_actionable=True,
        suggested_action="Refit with required original-scale deterministics enabled",
    ),

    # Diagnostics & Statistical
    "MODEL_NOT_DIAGNOSED": ErrorDefinition(
        code="MODEL_NOT_DIAGNOSED",
        category=ErrorCategory.DIAGNOSTICS,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=412,
        user_actionable=True,
        suggested_action="Call diagnose_mmm before using decision or optimization tools",
    ),
    "DIAGNOSTICS_FAILED": ErrorDefinition(
        code="DIAGNOSTICS_FAILED",
        category=ErrorCategory.DIAGNOSTICS,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Inspect fitted model artifact traces",
    ),
    "MODEL_REJECTED": ErrorDefinition(
        code="MODEL_REJECTED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Model failed diagnostic thresholds; review warnings and refit",
    ),
    "SAMPLING_FAILED": ErrorDefinition(
        code="SAMPLING_FAILED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Increase warmup draws, tune target_accept, or adjust priors",
    ),
    "NUMERICAL_INSTABILITY": ErrorDefinition(
        code="NUMERICAL_INSTABILITY",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Check media and target scaling, remove highly collinear channels, or adjust prior parameters",
    ),
    "SAMPLING_DIVERGED": ErrorDefinition(
        code="SAMPLING_DIVERGED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Increase target_accept or reparameterize priors to eliminate divergences",
    ),
    "POOR_CHAIN_CONVERGENCE": ErrorDefinition(
        code="POOR_CHAIN_CONVERGENCE",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.WARNING,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Increase draws and chains to achieve R-hat < 1.05",
    ),
    "INSUFFICIENT_EFFECTIVE_SAMPLE_SIZE": ErrorDefinition(
        code="INSUFFICIENT_EFFECTIVE_SAMPLE_SIZE",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.WARNING,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Increase draws or reduce autocorrelation with thinning",
    ),
    "POSTERIOR_PREDICTIVE_FAILED": ErrorDefinition(
        code="POSTERIOR_PREDICTIVE_FAILED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Verify out-of-sample predictor column alignment",
    ),
    "CALIBRATION_FAILED": ErrorDefinition(
        code="CALIBRATION_FAILED",
        category=ErrorCategory.CALIBRATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Review lift test inputs, variances, and channel names",
    ),
    "CROSS_VALIDATION_FAILED": ErrorDefinition(
        code="CROSS_VALIDATION_FAILED",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Check cross-validation folds, date spans, and step sizes",
    ),
    "PRIOR_SENSITIVITY_FAILED": ErrorDefinition(
        code="PRIOR_SENSITIVITY_FAILED",
        category=ErrorCategory.STATISTICAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Review prior scale multipliers and distribution types",
    ),
    "MODEL_COMPARISON_FAILED": ErrorDefinition(
        code="MODEL_COMPARISON_FAILED",
        category=ErrorCategory.MODEL_SELECTION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Ensure models expose log_likelihood for LOO/WAIC comparison",
    ),
    "INCOMPATIBLE_MODELS": ErrorDefinition(
        code="INCOMPATIBLE_MODELS",
        category=ErrorCategory.MODEL_SELECTION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=True,
        suggested_action="Compare only models fitted on identical dataset contents",
    ),

    # Optimization & Decisions
    "OPTIMIZATION_FAILED": ErrorDefinition(
        code="OPTIMIZATION_FAILED",
        category=ErrorCategory.OPTIMIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=422,
        user_actionable=True,
        suggested_action="Review budget bounds, constraints, and optimizer convergence diagnostics",
    ),
    "BUDGET_OPTIMIZATION_FAILED": ErrorDefinition(
        code="BUDGET_OPTIMIZATION_FAILED",
        category=ErrorCategory.OPTIMIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=422,
        user_actionable=True,
        suggested_action="Retry using a supported fallback initialization or inspect allocation constraints",
    ),
    "OPTIMIZATION_RESULT_INCOMPLETE": ErrorDefinition(
        code="OPTIMIZATION_RESULT_INCOMPLETE",
        category=ErrorCategory.OPTIMIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=422,
        user_actionable=False,
        suggested_action="Optimizer returned without recommended allocation",
    ),
    "BUDGET_SIMULATION_FAILED": ErrorDefinition(
        code="BUDGET_SIMULATION_FAILED",
        category=ErrorCategory.OPTIMIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Inspect scenario changes and baseline channel alignment",
    ),
    "FLIGHTING_OPTIMIZATION_FAILED": ErrorDefinition(
        code="FLIGHTING_OPTIMIZATION_FAILED",
        category=ErrorCategory.OPTIMIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=422,
        user_actionable=True,
        suggested_action="Review flighting time horizon and budget constraints",
    ),
    "INVALID_BUDGET": ErrorDefinition(
        code="INVALID_BUDGET",
        category=ErrorCategory.OPTIMIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Provide non-negative budget allocation values",
    ),
    "BUDGET_DATA_UNAVAILABLE": ErrorDefinition(
        code="BUDGET_DATA_UNAVAILABLE",
        category=ErrorCategory.OPTIMIZATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=409,
        user_actionable=True,
        suggested_action="Ensure model contains valid historical periods",
    ),

    # CLV
    "CLV_FIT_FAILED": ErrorDefinition(
        code="CLV_FIT_FAILED",
        category=ErrorCategory.CLV,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Verify RFM customer transaction distributions",
    ),
    "CLV_PREDICTION_FAILED": ErrorDefinition(
        code="CLV_PREDICTION_FAILED",
        category=ErrorCategory.CLV,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=True,
        suggested_action="Verify prediction horizon and customer ID alignment",
    ),
    "CLV_MODEL_NOT_FOUND": ErrorDefinition(
        code="CLV_MODEL_NOT_FOUND",
        category=ErrorCategory.CLV,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Fit a CLV model before querying predictions",
    ),
    "INVALID_CLV_MODEL_TYPE": ErrorDefinition(
        code="INVALID_CLV_MODEL_TYPE",
        category=ErrorCategory.CLV,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=True,
        suggested_action="Use a supported CLV model type (bg_nbd, pareto_nbd, gamma_gamma, shifted_beta_geo)",
    ),
    "CLV_LINEAGE_MISMATCH": ErrorDefinition(
        code="CLV_LINEAGE_MISMATCH",
        category=ErrorCategory.CLV,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=409,
        user_actionable=True,
        suggested_action="Ensure purchase and spend models were trained on identical customer cohorts and datasets",
    ),

    # Async Jobs
    "JOB_NOT_FOUND": ErrorDefinition(
        code="JOB_NOT_FOUND",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Check job_id or submit a new async job",
    ),
    "JOB_EXECUTION_FAILED": ErrorDefinition(
        code="JOB_EXECUTION_FAILED",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Inspect job error details for failed stage",
    ),
    "JOB_CANCELLED": ErrorDefinition(
        code="JOB_CANCELLED",
        category=ErrorCategory.CANCELLATION,
        severity=ErrorSeverity.INFO,
        retryable=False,
        http_status=409,
        user_actionable=True,
        suggested_action="Job was cancelled by caller or administrator",
    ),
    "JOB_RECOVERY_FAILED": ErrorDefinition(
        code="JOB_RECOVERY_FAILED",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Job state could not be recovered from checkpoints",
    ),
    "JOB_RESUME_FAILED": ErrorDefinition(
        code="JOB_RESUME_FAILED",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Job cannot be resumed from current checkpoint",
    ),
    "INVALID_JOB_STATE": ErrorDefinition(
        code="INVALID_JOB_STATE",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=409,
        user_actionable=False,
        suggested_action="Job is not in an eligible state for this transition",
    ),
    "STALE_JOB_CLAIM": ErrorDefinition(
        code="STALE_JOB_CLAIM",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.WARNING,
        retryable=True,
        http_status=409,
        user_actionable=False,
        suggested_action="Job lease expired or was reclaimed by another worker",
    ),
    "WORKER_EXECUTION_FAILED": ErrorDefinition(
        code="WORKER_EXECUTION_FAILED",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Worker process encountered an unhandled exception",
    ),
    "NO_HANDLER": ErrorDefinition(
        code="NO_HANDLER",
        category=ErrorCategory.JOB,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="No worker handler registered for this job type",
    ),

    # Persistence & Storage
    "PERSISTENCE_READ_FAILED": ErrorDefinition(
        code="PERSISTENCE_READ_FAILED",
        category=ErrorCategory.PERSISTENCE,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=500,
        user_actionable=False,
        suggested_action="Report error_id to the service operator",
    ),
    "PERSISTENCE_WRITE_FAILED": ErrorDefinition(
        code="PERSISTENCE_WRITE_FAILED",
        category=ErrorCategory.PERSISTENCE,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Report error_id to the service operator",
    ),
    "PERSISTENCE_SCHEMA_UNAVAILABLE": ErrorDefinition(
        code="PERSISTENCE_SCHEMA_UNAVAILABLE",
        category=ErrorCategory.PERSISTENCE,
        severity=ErrorSeverity.CRITICAL,
        retryable=False,
        http_status=503,
        user_actionable=False,
        suggested_action="Run database migrations to initialize persistence schema",
    ),
    "POSTERIOR_SAVE_FAILED": ErrorDefinition(
        code="POSTERIOR_SAVE_FAILED",
        category=ErrorCategory.PERSISTENCE,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Check disk capacity and artifact storage permissions",
    ),
    "ARTIFACT_NOT_FOUND": ErrorDefinition(
        code="ARTIFACT_NOT_FOUND",
        category=ErrorCategory.ARTIFACT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Verify artifact URI or regenerate model/plot artifact",
    ),
    "ARTIFACT_INTEGRITY_FAILED": ErrorDefinition(
        code="ARTIFACT_INTEGRITY_FAILED",
        category=ErrorCategory.ARTIFACT,
        severity=ErrorSeverity.CRITICAL,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Artifact checksum mismatch; regenerate artifact",
    ),
    "ARTIFACT_EXPORT_FAILED": ErrorDefinition(
        code="ARTIFACT_EXPORT_FAILED",
        category=ErrorCategory.ARTIFACT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Report error_id to the service operator",
    ),
    "BROKEN_ARTIFACT": ErrorDefinition(
        code="BROKEN_ARTIFACT",
        category=ErrorCategory.ARTIFACT,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=400,
        user_actionable=False,
        suggested_action="Artifact reference is malformed or inconsistent",
    ),
    "STORAGE_CLEANUP_FAILED": ErrorDefinition(
        code="STORAGE_CLEANUP_FAILED",
        category=ErrorCategory.ARTIFACT,
        severity=ErrorSeverity.WARNING,
        retryable=True,
        http_status=500,
        user_actionable=False,
        suggested_action="Some artifacts could not be deleted; review partial errors",
    ),

    # Resources & Network
    "PLOT_NOT_CACHED": ErrorDefinition(
        code="PLOT_NOT_CACHED",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.INFO,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Call get_posterior_plots first to generate the plot",
    ),
    "PLOT_RESOURCE_ERROR": ErrorDefinition(
        code="PLOT_RESOURCE_ERROR",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Error reading plot resource",
    ),
    "RESOURCE_NOT_FOUND": ErrorDefinition(
        code="RESOURCE_NOT_FOUND",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Verify resource identifier",
    ),
    "CREDENTIAL_NOT_FOUND": ErrorDefinition(
        code="CREDENTIAL_NOT_FOUND",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=404,
        user_actionable=True,
        suggested_action="Verify credential_id",
    ),
    "UPSTREAM_HTTP_ERROR": ErrorDefinition(
        code="UPSTREAM_HTTP_ERROR",
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=502,
        user_actionable=False,
        suggested_action="Check upstream service health",
    ),
    "UPSTREAM_TIMEOUT": ErrorDefinition(
        code="UPSTREAM_TIMEOUT",
        category=ErrorCategory.TIMEOUT,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=504,
        user_actionable=False,
        suggested_action="Retry request after delay",
    ),
    "UPSTREAM_UNAVAILABLE": ErrorDefinition(
        code="UPSTREAM_UNAVAILABLE",
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=503,
        user_actionable=False,
        suggested_action="Upstream host unavailable; retry later",
    ),
    "UNREACHABLE_SOURCE": ErrorDefinition(
        code="UNREACHABLE_SOURCE",
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.ERROR,
        retryable=True,
        http_status=502,
        user_actionable=True,
        suggested_action="Verify that hostname is valid, reachable, and resolvable",
    ),
    "DEPENDENCY_UNAVAILABLE": ErrorDefinition(
        code="DEPENDENCY_UNAVAILABLE",
        category=ErrorCategory.DEPENDENCY,
        severity=ErrorSeverity.CRITICAL,
        retryable=True,
        http_status=503,
        user_actionable=False,
        suggested_action="Service dependency is unavailable; check system health",
    ),
    "CONFIGURATION_INVALID": ErrorDefinition(
        code="CONFIGURATION_INVALID",
        category=ErrorCategory.CONFIGURATION,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Verify server settings and environment configuration",
    ),
    "RESOURCE_LIMIT_EXCEEDED": ErrorDefinition(
        code="RESOURCE_LIMIT_EXCEEDED",
        category=ErrorCategory.RESOURCE,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=429,
        user_actionable=True,
        suggested_action="Throttle request rate or upload smaller payloads",
    ),
    "INTERNAL_ERROR": ErrorDefinition(
        code="INTERNAL_ERROR",
        category=ErrorCategory.INTERNAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Report the error_id to the service operator",
    ),
}


def get_error_definition(code: str) -> ErrorDefinition:
    """Retrieve catalog definition for a code or construct a fallback definition."""
    if code in ERROR_CATALOG:
        return ERROR_CATALOG[code]
    return ErrorDefinition(
        code=code,
        category=ErrorCategory.INTERNAL,
        severity=ErrorSeverity.ERROR,
        retryable=False,
        http_status=500,
        user_actionable=False,
        suggested_action="Report the error_id to the service operator",
    )


class OriginalErrorInfo(BaseModel):
    """Typed details about the underlying root cause exception."""

    model_config = ConfigDict(extra="ignore")

    type: str
    module: str | None = None
    message: str = ""
    code: str | int | None = None


class NormalizedError(BaseModel):
    """Canonical internal normalized error model across all platform subsystems."""

    model_config = ConfigDict(extra="ignore")

    error_id: str = Field(default_factory=generate_error_id)
    code: str
    category: str
    severity: str = "error"

    message: str
    user_message: str | None = None

    operation: str | None = None
    component: str | None = None
    stage: str | None = None

    retryable: bool = False
    user_actionable: bool = False

    original_error: OriginalErrorInfo | None = None
    cause_chain: list[OriginalErrorInfo] = Field(default_factory=list)

    context: dict[str, Any] = Field(default_factory=dict)
    evidence: dict[str, Any] = Field(default_factory=dict)

    request_id: str | None = None
    job_id: str | None = None
    dataset_id: str | None = None
    model_id: str | None = None
    tenant_id: str | None = None
    artifact_uri: str | None = None

    suggested_action: str | None = None
    next_action: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    stack_trace: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """Produce safe, redacted public MCP error envelope dictionary."""
        from marketing_mcp.security.redaction import redact_secrets

        action = self.suggested_action or self.next_action
        msg = self.message
        evidence = dict(self.evidence) if self.evidence else None

        if self.code == "AUTH_FORBIDDEN":
            import re
            msg = re.sub(r"belonging to tenant '[^']+'", "belonging to another tenant", msg)
            if evidence and "record_tenant" in evidence:
                evidence = dict(evidence)
                evidence.pop("record_tenant", None)

        payload: dict[str, Any] = {
            "error_id": self.error_id,
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": msg,
            "retryable": self.retryable,
            "user_actionable": self.user_actionable,
            "timestamp": self.timestamp,
        }

        if action:
            payload["suggested_action"] = action
            payload["next_action"] = action

        if evidence:
            payload["evidence"] = evidence

        if self.original_error is not None:
            orig_dict: dict[str, Any] = {
                "type": self.original_error.type,
                "message": self.original_error.message,
            }
            if self.original_error.module:
                orig_dict["module"] = self.original_error.module
            if self.original_error.code is not None:
                orig_dict["code"] = self.original_error.code
            payload["original_error"] = orig_dict

        if self.context:
            payload["context"] = self.context

        return redact_secrets(payload)

    def to_mcp_response(self) -> dict[str, Any]:
        """Wrap public dictionary in canonical MCP top-level envelope."""
        return {"error": self.to_public_dict()}

    def to_diagnostic_dict(self) -> dict[str, Any]:
        """Produce technical diagnostic event for structured logs and operator registry."""
        from marketing_mcp.security.redaction import redact_secrets

        raw = {
            "event": "operation_failed",
            "error_id": self.error_id,
            "code": self.code,
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "operation": self.operation,
            "component": self.component,
            "stage": self.stage,
            "retryable": self.retryable,
            "user_actionable": self.user_actionable,
            "request_id": self.request_id,
            "job_id": self.job_id,
            "dataset_id": self.dataset_id,
            "model_id": self.model_id,
            "tenant_id": self.tenant_id,
            "artifact_uri": self.artifact_uri,
            "suggested_action": self.suggested_action or self.next_action,
            "original_error": self.original_error.model_dump() if self.original_error else None,
            "cause_chain": [c.model_dump() for c in self.cause_chain],
            "context": self.context,
            "evidence": self.evidence,
            "stack_trace": self.stack_trace,
        }
        return redact_secrets(raw)


class DomainError(Exception):
    """Domain-specific exception that carries structured error properties."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        evidence: Any = None,
        next_action: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        retryable: bool | None = None,
        user_actionable: bool | None = None,
        suggested_action: str | None = None,
        context: dict[str, Any] | None = None,
        original_error: OriginalErrorInfo | dict[str, Any] | None = None,
        error_id: str | None = None,
        cause_chain: list[OriginalErrorInfo] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.evidence = evidence or {}
        self.next_action = next_action or suggested_action
        self.suggested_action = suggested_action or next_action

        defn = get_error_definition(code)
        self.category = category or defn.category.value
        self.severity = severity or defn.severity.value
        self.retryable = retryable if retryable is not None else defn.retryable
        self.user_actionable = user_actionable if user_actionable is not None else defn.user_actionable
        if not self.suggested_action and defn.suggested_action:
            self.suggested_action = defn.suggested_action
            self.next_action = self.suggested_action

        self.context = context or {}
        self.error_id = error_id or generate_error_id()
        self.cause_chain = cause_chain or []

        if isinstance(original_error, dict):
            self.original_error = OriginalErrorInfo(**original_error)
        elif isinstance(original_error, OriginalErrorInfo):
            self.original_error = original_error
        else:
            self.original_error = None

    def to_normalized(self) -> NormalizedError:
        """Convert DomainError to canonical NormalizedError."""
        orig_err = self.original_error
        causes: list[OriginalErrorInfo] = list(self.cause_chain)

        if orig_err is None and self.__cause__ is not None:
            cause_exc = self.__cause__
            orig_err = OriginalErrorInfo(
                type=type(cause_exc).__name__,
                module=getattr(type(cause_exc), "__module__", None),
                message=str(cause_exc),
                code=getattr(cause_exc, "code", getattr(cause_exc, "status_code", None)),
            )
            curr = getattr(cause_exc, "__cause__", None)
            while curr is not None and len(causes) < 10:
                causes.append(
                    OriginalErrorInfo(
                        type=type(curr).__name__,
                        module=getattr(type(curr), "__module__", None),
                        message=str(curr),
                        code=getattr(curr, "code", getattr(curr, "status_code", None)),
                    )
                )
                curr = getattr(curr, "__cause__", None)

        evidence_dict = self.evidence if isinstance(self.evidence, dict) else {"details": self.evidence}

        return NormalizedError(
            error_id=self.error_id,
            code=self.code,
            category=self.category,
            severity=self.severity,
            message=self.message,
            retryable=self.retryable,
            user_actionable=self.user_actionable,
            suggested_action=self.suggested_action,
            next_action=self.next_action,
            evidence=evidence_dict,
            context=self.context,
            original_error=orig_err,
            cause_chain=causes,
        )

    def to_dict(self) -> dict[str, Any]:
        """Backward-compatible envelope serialization."""
        return self.to_normalized().to_mcp_response()

    def to_mcp_response(self) -> dict[str, Any]:
        """Wrap public dictionary in canonical MCP top-level envelope."""
        return self.to_dict()


__all__ = [
    "ERROR_CATALOG",
    "DomainError",
    "ErrorCategory",
    "ErrorDefinition",
    "ErrorSeverity",
    "NormalizedError",
    "OriginalErrorInfo",
    "generate_error_id",
    "get_error_definition",
]
