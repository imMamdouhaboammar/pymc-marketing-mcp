"""Posterior utility objective abstraction.

Pluggable protocol that transforms posterior outcome samples plus financial
assumptions into a scalar optimization utility.  The first implementation
(``ExpectedResponseObjective``) reproduces the existing ``maximize_response``
behaviour exactly so no existing test can regress.

New risk-aware objectives are added here only after a scientific RFC and
invariant tests confirm their semantics.

Design rule (from roadmap): objective evaluation must consume posterior samples
returned by the current model path — it must NOT reimplement model response
math independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import numpy as np

from marketing_mcp.domain.decisions.financial import FinancialAssumptions

ObjectiveName = str  # one of the registered objective keys


@runtime_checkable
class UtilityObjective(Protocol):
    """Protocol every optimization objective must satisfy.

    ``evaluate`` receives a 1-D posterior sample array (shape: [n_draws]) and
    the financial assumptions, and returns a single scalar utility.  The
    optimizer maximises this value.
    """

    @property
    def name(self) -> str:
        ...

    def evaluate(
        self,
        posterior_samples: np.ndarray,
        financial: FinancialAssumptions,
        spend: float,
    ) -> float:
        """Return scalar utility (higher = better)."""
        ...

    def metadata(self) -> dict[str, Any]:
        """Return objective definition for provenance attachment."""
        ...


@dataclass(frozen=True)
class ExpectedResponseObjective:
    """Expected posterior response — reproduces existing maximize_response behaviour.

    Utility = E[response] — identical to the pre-contract path, so any
    existing allocation test must produce results within numerical tolerance.
    """

    name: str = "expected_response"

    def evaluate(
        self,
        posterior_samples: np.ndarray,
        financial: FinancialAssumptions,  # noqa: ARG002 — unused, kept for protocol parity
        spend: float,  # noqa: ARG002 — unused, kept for protocol parity
    ) -> float:
        return float(np.mean(posterior_samples))

    def metadata(self) -> dict[str, Any]:
        return {"objective": self.name, "description": "Expected value of posterior response samples"}


@dataclass(frozen=True)
class ExpectedNetProfitObjective:
    """Expected posterior net profit = E[revenue × margin − spend].

    Replaces the inline ``maximize_net_profit`` path in flighting.py with the
    canonical financial contract.  Behaviour is preserved exactly for the
    legacy ``margin_pct`` path via ``FinancialAssumptions.from_legacy()``.
    """

    name: str = "expected_net_profit"

    def evaluate(
        self,
        posterior_samples: np.ndarray,
        financial: FinancialAssumptions,
        spend: float,
    ) -> float:
        margin = financial.effective_margin_rate()
        rev_per = financial.revenue_per_outcome
        revenue = posterior_samples * rev_per
        net_profit = revenue * margin - spend
        return float(np.mean(net_profit))

    def metadata(self) -> dict[str, Any]:
        return {
            "objective": self.name,
            "description": "Expected net profit: E[revenue × margin_rate − spend]",
        }


# Registry — add new objectives here only with scientific RFC + invariant tests
_OBJECTIVE_REGISTRY: dict[str, UtilityObjective] = {
    "expected_response": ExpectedResponseObjective(),
    "expected_net_profit": ExpectedNetProfitObjective(),
    # ponytail: target_roas and risk-aware objectives added when RFC + tests exist
}


def get_objective(name: str) -> UtilityObjective:
    """Resolve objective by name; raises ValueError with available names on miss."""
    obj = _OBJECTIVE_REGISTRY.get(name)
    if obj is None:
        available = sorted(_OBJECTIVE_REGISTRY)
        raise ValueError(f"Unknown objective {name!r}. Available: {available}")
    return obj


def objective_names() -> list[str]:
    return sorted(_OBJECTIVE_REGISTRY)
