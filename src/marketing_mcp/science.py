"""Pure scientific core decoupled from MCP and HTTP transport layers."""

from __future__ import annotations

from typing import Any
import pandas as pd

from marketing_mcp.diagnostic_gates import evaluate_decision_gate
from marketing_mcp.models.diagnostic_models import GateVerdict, DiagnosticGateEvaluation

__all__ = [
    "evaluate_decision_gate",
    "GateVerdict",
    "DiagnosticGateEvaluation",
]
