from __future__ import annotations

from dataclasses import dataclass

from marketing_mcp.errors import DomainError


@dataclass
class DecisionGate:
    decision_status: str
    failures: list[dict]

    def require_decision_access(self):
        if self.decision_status == "rejected":
            raise DomainError(
                "MODEL_NOT_VALIDATED",
                "Decision tools are disabled because the model failed diagnostic checks",
                evidence={"failures": self.failures},
                next_action="Improve or refit the model, then run diagnose_mmm again",
            )
