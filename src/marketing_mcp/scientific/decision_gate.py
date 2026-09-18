"""Pure Python diagnostics and decision policy gate evaluating MCMC convergence metrics."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

from marketing_mcp.errors import DomainError

try:
    from packages.contracts.python.models import (
        DiagnosticMetrics as PlatformDiagnosticMetrics,
        DiagnosticReport as PlatformDiagnosticReport,
    )
except ImportError:
    PlatformDiagnosticMetrics = None
    PlatformDiagnosticReport = None


class DecisionPolicyVerdict(str, Enum):
    PASS = "pass"
    CAUTION = "caution"
    BLOCK = "block"


class LocalDiagnosticMetrics(BaseModel):
    max_rhat: float
    divergences: int = Field(ge=0)
    min_bfmi: float
    rhat_ok: bool = True
    divergences_ok: bool = True
    bfmi_ok: bool = True


class LocalDiagnosticReport(BaseModel):
    schema_version: str = "1.0"
    run_id: UUID
    policy_version: str = "1.0.0"
    decision_status: Literal["pass", "caution", "block"]
    diagnostics: LocalDiagnosticMetrics
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _evaluate_metric_verdicts(
    max_rhat: float,
    divergences: int,
    min_bfmi: float,
) -> tuple[DecisionPolicyVerdict, bool, bool, bool, list[str]]:
    """Determine threshold compliance and policy verdict for convergence metrics."""
    reasons: list[str] = []
    verdicts: list[DecisionPolicyVerdict] = []

    # 1. Evaluate Max R-hat
    rhat_ok = max_rhat <= 1.05
    if max_rhat > 1.05:
        verdicts.append(DecisionPolicyVerdict.BLOCK)
        reasons.append(f"Max R-hat ({max_rhat:.4f}) exceeds blocking threshold 1.05")
    elif max_rhat > 1.01:
        verdicts.append(DecisionPolicyVerdict.CAUTION)
        reasons.append(f"Max R-hat ({max_rhat:.4f}) is elevated above 1.01")
    else:
        verdicts.append(DecisionPolicyVerdict.PASS)

    # 2. Evaluate Divergences
    divergences_ok = divergences == 0
    if divergences > 5:
        verdicts.append(DecisionPolicyVerdict.BLOCK)
        reasons.append(f"Divergences count ({divergences}) exceeds blocking threshold 5")
    elif divergences > 0:
        verdicts.append(DecisionPolicyVerdict.CAUTION)
        reasons.append(f"Observed {divergences} divergent transition(s)")
    else:
        verdicts.append(DecisionPolicyVerdict.PASS)

    # 3. Evaluate Min BFMI
    bfmi_ok = min_bfmi >= 0.2
    if min_bfmi < 0.2:
        verdicts.append(DecisionPolicyVerdict.BLOCK)
        reasons.append(f"Min BFMI ({min_bfmi:.4f}) is below blocking threshold 0.20")
    elif min_bfmi < 0.3:
        verdicts.append(DecisionPolicyVerdict.CAUTION)
        reasons.append(f"Min BFMI ({min_bfmi:.4f}) is marginal (below 0.30)")
    else:
        verdicts.append(DecisionPolicyVerdict.PASS)

    # Aggregate overall verdict
    if DecisionPolicyVerdict.BLOCK in verdicts:
        overall = DecisionPolicyVerdict.BLOCK
    elif DecisionPolicyVerdict.CAUTION in verdicts:
        overall = DecisionPolicyVerdict.CAUTION
    else:
        overall = DecisionPolicyVerdict.PASS

    return overall, rhat_ok, divergences_ok, bfmi_ok, reasons


def evaluate_diagnostic_policy(
    run_id: str | UUID,
    max_rhat: float,
    divergences: int,
    min_bfmi: float,
    policy_version: str = "1.0.0",
) -> Any:
    """Evaluate MCMC convergence metrics against canonical server decision gate policy."""
    parsed_id = UUID(str(run_id)) if not isinstance(run_id, UUID) else run_id
    verdict, rhat_ok, div_ok, bfmi_ok, reasons = _evaluate_metric_verdicts(
        max_rhat=max_rhat,
        divergences=divergences,
        min_bfmi=min_bfmi,
    )

    metrics_cls = PlatformDiagnosticMetrics or LocalDiagnosticMetrics
    report_cls = PlatformDiagnosticReport or LocalDiagnosticReport

    metrics = metrics_cls(
        max_rhat=max_rhat,
        divergences=divergences,
        min_bfmi=min_bfmi,
        rhat_ok=rhat_ok,
        divergences_ok=div_ok,
        bfmi_ok=bfmi_ok,
    )

    return report_cls(
        schema_version="1.0",
        run_id=parsed_id,
        policy_version=policy_version,
        decision_status=verdict.value,
        diagnostics=metrics,
        reasons=reasons,
        evaluated_at=datetime.now(timezone.utc),
    )


def enforce_decision_gate(
    report: Any,
    action: str = "optimize_budget",
) -> None:
    """Enforce server-side diagnostic gate, raising DomainError if model is blocked."""
    status = getattr(report, "decision_status", None)
    if status == "block":
        reasons = getattr(report, "reasons", [])
        raise DomainError(
            code="MODEL_NOT_VALIDATED",
            message=f"Action '{action}' is blocked by server diagnostic policy gate (status: {status})",
            evidence={
                "action": action,
                "decision_status": status,
                "reasons": reasons,
                "diagnostics": report.diagnostics.model_dump() if hasattr(report.diagnostics, "model_dump") else str(report.diagnostics),
            },
            next_action="Review MCMC convergence, increase draws or target_accept, or reformulate priors",
        )
