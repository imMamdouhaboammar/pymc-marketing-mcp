"""Pure scientific core decoupled from MCP and HTTP transport layers."""

from __future__ import annotations

from marketing_mcp.diagnostic_gates import evaluate_decision_gate
from marketing_mcp.models.diagnostic_models import DiagnosticGateEvaluation, GateVerdict

__all__ = [
    "DiagnosticGateEvaluation",
    "GateVerdict",
    "evaluate_decision_gate",
]
