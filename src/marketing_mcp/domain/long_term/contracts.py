"""Domain contracts for Long-Term Brand Effects and VAR Integration (T8)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ImpulseResponseCurve(BaseModel):
    """Impulse response of a target variable to an exogenous media investment shock."""

    channel: str = Field(description="Exogenous media channel shocked")
    target: str = Field(description="Endogenous outcome variable (e.g. brand_equity, revenue)")
    horizons: list[int] = Field(description="Time lag horizon steps (0, 1, ..., H)")
    responses: list[float] = Field(description="Response magnitude at each horizon step")
    cumulative_multiplier: float = Field(
        description=(
            "Finite-horizon cumulative response divided by contemporaneous response: "
            "(total response over H) / (initial impact)"
        )
    )


class LongTermRollup(BaseModel):
    """Long-term effects rollup; decision attachment depends on engine-specific evidence gates."""

    model_id: str = Field(description="Identifier of the VAR long-term model")
    tenant_id: str = Field(default="default", description="Tenant/organization identifier")
    endogenous_columns: list[str] = Field(description="Endogenous variables (brand equity, sales, etc.)")
    exogenous_channels: list[str] = Field(description="Exogenous media channels")
    channel_multipliers: dict[str, float] = Field(
        description=(
            "Finite-horizon cumulative response divided by contemporaneous response per channel; "
            "may be below 1.0 when later responses offset the initial effect"
        )
    )
    irfs: dict[str, ImpulseResponseCurve] = Field(
        default_factory=dict, description="Detailed IRF curves keyed by channel name"
    )
    max_eigenvalue: float = Field(description="Maximum companion matrix eigenvalue modulus")
    is_stationary: bool = Field(description="True if all characteristic roots lie inside unit circle")
    diagnostic_status: str = Field(
        default="pass", description="Gate verdict: pass, caution, or rejected"
    )
    provenance: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class LongTermEffectsEngine(Protocol):
    """Protocol for long-term brand effect estimation engines."""

    def fit_var(
        self,
        df: Any,
        endogenous_columns: list[str],
        exogenous_channels: list[str],
        horizon: int = 12,
        tenant_id: str = "default",
    ) -> LongTermRollup:
        """Fit vector autoregression and compute impulse response rollups."""
        ...

    def rollup_into_decision(
        self,
        decision_result: dict[str, Any],
        rollup: LongTermRollup,
    ) -> dict[str, Any]:
        """Attach only decision-grade rollups; implementations must fail closed otherwise."""
        ...
