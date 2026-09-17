from __future__ import annotations

from dataclasses import dataclass, field

from marketing_mcp.errors import DomainError


@dataclass
class DecisionReadiness:
    status: str
    model_id: str
    dataset_id: str
    dataset_fingerprint: str | None = None
    passed_checks: list[str] = field(default_factory=list)
    failed_checks: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    blocked_actions: list[str] = field(default_factory=list)
    decision_eligible: bool = True
    mode: str = "production"
    audit_watermark: str | None = None


@dataclass
class DecisionGate:
    decision_status: str
    failures: list[dict] = field(default_factory=list)
    model_id: str = ""
    dataset_id: str = ""
    dataset_fingerprint: str | None = None
    mode: str = "production"  # "production" or "exploratory"

    def evaluate_readiness(self) -> DecisionReadiness:
        is_blocked = self.decision_status in (
            "rejected",
            "blocked",
            "blocked_predictive_failure",
            "blocked_sampler_failure",
            "blocked_data_quality",
        ) or bool(self.failures)

        decision_eligible = not is_blocked
        passed_checks = []
        failed_checks = []

        if not is_blocked:
            passed_checks.extend(["mcmc_sampler_convergence", "in_sample_ppc", "out_of_sample_predictive_validity"])
            allowed = ["optimize_budget", "simulate_budget", "optimize_flighting", "get_incremental_roas", "get_response_curves"]
            blocked = []
            audit_wm = None
        else:
            for f in self.failures:
                msg = f.get("message") if isinstance(f, dict) else str(f)
                failed_checks.append(msg)
            if not failed_checks:
                failed_checks.append(f"Model validation state is {self.decision_status}")

            if self.mode == "exploratory":
                # In exploratory mode, analytical inspection is permitted with audit watermark
                allowed = ["simulate_budget", "get_response_curves", "get_channel_contributions"]
                blocked = ["optimize_budget", "optimize_flighting"]
                audit_wm = "EXPLORATORY_ANALYSIS_ONLY: NOT_FOR_COMMERCIAL_BUDGET_REALLOCATION"
            else:
                allowed = []
                blocked = ["optimize_budget", "simulate_budget", "optimize_flighting", "get_incremental_roas", "get_response_curves"]
                audit_wm = "BLOCKED_DECISION_GATE"

        return DecisionReadiness(
            status=self.decision_status,
            model_id=self.model_id,
            dataset_id=self.dataset_id,
            dataset_fingerprint=self.dataset_fingerprint,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            allowed_actions=allowed,
            blocked_actions=blocked,
            decision_eligible=decision_eligible,
            mode=self.mode,
            audit_watermark=audit_wm,
        )

    def require_decision_access(self, action: str = "optimize_budget") -> DecisionReadiness:
        readiness = self.evaluate_readiness()
        if not readiness.decision_eligible:
            if self.mode == "exploratory" and action in readiness.allowed_actions:
                return readiness
            raise DomainError(
                "MODEL_NOT_VALIDATED",
                f"Decision tools are disabled because the model failed diagnostic checks (status: {self.decision_status})",
                evidence={
                    "status": self.decision_status,
                    "failures": self.failures,
                    "mode": self.mode,
                    "action_requested": action,
                    "blocked_actions": readiness.blocked_actions,
                    "failed_checks": readiness.failed_checks,
                },
                next_action="Improve or refit the model, review out-of-sample predictive accuracy, and run diagnose_mmm again",
            )
        return readiness
