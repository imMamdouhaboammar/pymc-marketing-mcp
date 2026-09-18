"""Canonical typed financial contract for all decision tools.

Single source of truth for financial semantics across budget optimization,
flighting, simulation, CLV, and future portfolio decisions.

Replaces the scattered ``margin_pct`` / ``discount_rate`` fields with one
typed contract that is requested, resolved, and persisted explicitly.
``margin_pct`` is kept as a legacy alias through the ``from_legacy`` adapter
so all existing public schemas remain backward-compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

KPIUnit = Literal["revenue", "conversions", "leads", "custom"]
DiscountConvention = Literal["periodic", "annual"]


@dataclass(frozen=True)
class FinancialAssumptions:
    """All financial parameters consumed by any decision tool.

    Attributes
    ----------
    kpi_unit:
        What the model target represents (revenue, conversions, …).
    revenue_per_outcome:
        Scaling factor converting model outcome units to monetary revenue.
        Set to 1.0 when the target is already in currency units.
    gross_margin_rate:
        Gross margin as a fraction of revenue (0–1).  Replaces ``margin_pct``.
    contribution_margin_rate:
        Contribution margin (gross margin minus variable costs) as a fraction.
        Defaults to ``gross_margin_rate`` when not supplied separately.
    variable_cost_per_unit:
        Variable cost per outcome unit, alternative to rate-based margin.
    acquisition_cost:
        Cost to acquire one customer/lead, used for CPA-aware objectives.
    customer_lifetime_value_ref:
        Reference CLV used in LTV-aware optimization.
    discount_rate:
        Periodic discount rate for NPV/CLV calculations (0–1).
    discount_convention:
        Whether ``discount_rate`` is per-period or annual.
    planning_horizon:
        Number of periods for NPV rolling; ``None`` uses the model default.
    """

    kpi_unit: KPIUnit = "revenue"
    revenue_per_outcome: float = 1.0
    gross_margin_rate: float = 1.0
    contribution_margin_rate: float | None = None  # falls back to gross_margin_rate
    variable_cost_per_unit: float | None = None
    acquisition_cost: float | None = None
    customer_lifetime_value_ref: float | None = None
    discount_rate: float = 0.0
    discount_convention: DiscountConvention = "periodic"
    planning_horizon: int | None = None

    # ponytail: frozen dataclass — no accidental mutation; equality is value-based
    def effective_margin_rate(self) -> float:
        """Return the margin rate actually used in net-profit calculations."""
        if self.contribution_margin_rate is not None:
            return self.contribution_margin_rate
        return self.gross_margin_rate

    def to_provenance(self) -> dict[str, Any]:
        """Serialise for decision provenance attachment."""
        return {
            "kpi_unit": self.kpi_unit,
            "revenue_per_outcome": self.revenue_per_outcome,
            "gross_margin_rate": self.gross_margin_rate,
            "contribution_margin_rate": self.contribution_margin_rate,
            "variable_cost_per_unit": self.variable_cost_per_unit,
            "acquisition_cost": self.acquisition_cost,
            "customer_lifetime_value_ref": self.customer_lifetime_value_ref,
            "discount_rate": self.discount_rate,
            "discount_convention": self.discount_convention,
            "planning_horizon": self.planning_horizon,
        }

    @staticmethod
    def from_legacy(margin_pct: float = 1.0, discount_rate: float = 0.0) -> "FinancialAssumptions":
        """Backward-compatible adapter for callers still passing ``margin_pct``.

        Preserves existing net-profit flighting behavior exactly.
        """
        return FinancialAssumptions(
            gross_margin_rate=float(margin_pct),
            discount_rate=float(discount_rate),
        )

    def validate(self) -> list[str]:
        """Return list of unit/semantic errors; empty means valid."""
        errors: list[str] = []
        if not (0.0 <= self.gross_margin_rate <= 1.0):
            errors.append(f"gross_margin_rate {self.gross_margin_rate} outside [0, 1]")
        if self.contribution_margin_rate is not None and not (
            0.0 <= self.contribution_margin_rate <= 1.0
        ):
            errors.append(
                f"contribution_margin_rate {self.contribution_margin_rate} outside [0, 1]"
            )
        if not (0.0 <= self.discount_rate <= 1.0):
            errors.append(f"discount_rate {self.discount_rate} outside [0, 1]")
        if self.revenue_per_outcome < 0:
            errors.append("revenue_per_outcome must be non-negative")
        if self.variable_cost_per_unit is not None and self.variable_cost_per_unit < 0:
            errors.append("variable_cost_per_unit must be non-negative")
        return errors
