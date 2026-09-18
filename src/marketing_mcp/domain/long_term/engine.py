"""Deterministic ridge VARX long-term brand-effects prototype (T8 - Experimental)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from marketing_mcp.domain.long_term.contracts import (
    ImpulseResponseCurve,
    LongTermEffectsEngine,
    LongTermRollup,
)
from marketing_mcp.errors import DomainError


class DeterministicVARLongTermEngine(LongTermEffectsEngine):
    """Deterministic ridge VARX prototype for descriptive long-term effects.

    This engine produces point estimates only. It does not perform posterior sampling
    and must not be used as decision-grade Bayesian evidence.
    """

    def fit_var(
        self,
        df: pd.DataFrame,
        endogenous_columns: list[str],
        exogenous_channels: list[str],
        horizon: int = 12,
        tenant_id: str = "default",
    ) -> LongTermRollup:
        """Fit stationary VARX(1) model and compute impulse response rollups."""
        m_endo = len(endogenous_columns)
        k_exo = len(exogenous_channels)
        if m_endo < 1:
            raise DomainError("INPUT_INVALID", "At least one endogenous variable is required")
        if k_exo < 1:
            raise DomainError("INPUT_INVALID", "At least one exogenous media channel is required")
        if len(set(endogenous_columns)) != m_endo:
            raise DomainError("INPUT_INVALID", "Endogenous columns must be unique")
        if len(set(exogenous_channels)) != k_exo:
            raise DomainError("INPUT_INVALID", "Exogenous channels must be unique")
        overlap = sorted(set(endogenous_columns) & set(exogenous_channels))
        if overlap:
            raise DomainError(
                "INPUT_INVALID",
                "Endogenous and exogenous columns must be disjoint",
                evidence={"overlapping_columns": overlap},
            )

        # Extract numeric matrices
        for col in endogenous_columns + exogenous_channels:
            if col not in df.columns:
                raise DomainError("INPUT_INVALID", f"Column '{col}' not found in dataset")

        selected_columns = endogenous_columns + exogenous_channels
        numeric = pd.DataFrame(
            {col: pd.to_numeric(df[col], errors="coerce") for col in selected_columns},
            index=df.index,
        ).dropna()
        if len(numeric) < 16:
            raise DomainError(
                "DATASET_TOO_SHORT",
                f"Dataset length ({len(numeric)}) is too short for VAR identification "
                "(minimum 16 jointly observed periods required)",
            )

        y = numeric[endogenous_columns].to_numpy(dtype=float)
        x = numeric[exogenous_channels].to_numpy(dtype=float)

        # Time series alignment for VAR(1): Y_t against Y_{t-1} and X_t
        y_curr = y[1:]  # shape: (T-1, m_endo)
        y_lag = y[:-1]  # shape: (T-1, m_endo)
        x_curr = x[1:]  # shape: (T-1, k_exo)
        t_obs = len(y_curr)

        # Regressors matrix Z = [Y_lag, X_curr, 1]
        ones = np.ones((t_obs, 1))
        z = np.hstack([y_lag, x_curr, ones])

        # Ridge regularization to ensure a well-conditioned deterministic solve.
        ridge_diag = np.ones(z.shape[1]) * 1e-4
        # Apply stronger shrinkage to all lag coefficients than exogenous/intercept terms.
        ridge_diag[:m_endo] = 1e-2
        reg_matrix = np.diag(ridge_diag)

        # Ridge-regularized least-squares coefficients: Beta = (Z'Z + Lambda)^(-1) Z'Y
        beta = np.linalg.solve(z.T @ z + reg_matrix, z.T @ y_curr)  # shape: (m_endo + k_exo + 1, m_endo)

        # Extract A (transition matrix) and B (exogenous impact matrix)
        # Note: z @ beta = y_lag @ A + x_curr @ B + intercept
        a_matrix = beta[:m_endo, :].T  # shape: (m_endo, m_endo)
        b_matrix = beta[m_endo : m_endo + k_exo, :].T  # shape: (m_endo, k_exo)

        # Eigenvalue stability check: all characteristic roots of A must have modulus < 1
        eigenvals = np.linalg.eigvals(a_matrix)
        max_eigenval = float(np.max(np.abs(eigenvals)))
        is_stationary = max_eigenval < 1.0

        diagnostic_status = "pass" if max_eigenval < 0.95 else ("caution" if is_stationary else "rejected")

        # Compute Impulse Response Functions (IRFs) over horizon H
        target_idx = m_endo - 1  # Assume last endogenous column is primary business KPI (revenue)
        target_name = endogenous_columns[target_idx]

        irfs: dict[str, ImpulseResponseCurve] = {}
        channel_multipliers: dict[str, float] = {}

        for k_idx, ch in enumerate(exogenous_channels):
            # Unit impulse in channel k
            # Initial contemporaneous impact at h=0:
            impulse_0 = b_matrix[:, k_idx]
            resp_h = [float(impulse_0[target_idx])]

            current_impact = impulse_0.copy()
            for h in range(1, horizon + 1):
                current_impact = a_matrix @ current_impact
                resp_h.append(float(current_impact[target_idx]))

            initial_val = float(resp_h[0])
            cum_val = float(sum(resp_h))
            if abs(initial_val) < 1e-8:
                raise DomainError(
                    "LONG_TERM_MULTIPLIER_UNDEFINED",
                    f"Channel '{ch}' has near-zero contemporaneous target impact; "
                    "the cumulative-to-initial multiplier is undefined",
                    evidence={"channel": ch, "initial_target_impact": initial_val},
                    next_action=(
                        "Choose a target/channel with non-zero contemporaneous impact, or use "
                        "an analysis path that reports raw impulse responses without a ratio multiplier"
                    ),
                )
            mult = round(cum_val / initial_val, 3)

            channel_multipliers[ch] = mult
            irfs[ch] = ImpulseResponseCurve(
                channel=ch,
                target=target_name,
                horizons=list(range(horizon + 1)),
                responses=[round(r, 4) for r in resp_h],
                cumulative_multiplier=mult,
            )

        now = datetime.now(UTC).isoformat()
        return LongTermRollup(
            model_id=f"var_{uuid.uuid4().hex[:10]}",
            tenant_id=tenant_id,
            endogenous_columns=endogenous_columns,
            exogenous_channels=exogenous_channels,
            channel_multipliers=channel_multipliers,
            irfs=irfs,
            max_eigenvalue=round(max_eigenval, 4),
            is_stationary=is_stationary,
            diagnostic_status=diagnostic_status,
            provenance={
                "fitted_at": now,
                "engine": "DeterministicVARLongTermEngine",
                "estimation_method": "ridge_regularized_least_squares",
                "uncertainty_quantified": False,
                "horizon": horizon,
                "experimental": True,
            },
        )

    def rollup_into_decision(
        self,
        decision_result: dict[str, Any],
        rollup: LongTermRollup,
    ) -> dict[str, Any]:
        """Refuse decision-grade rollup because this estimator has no posterior uncertainty."""
        if rollup.diagnostic_status == "rejected":
            raise DomainError(
                "LONG_TERM_GATE_REJECTED",
                f"Long-term VAR model has non-stationary explosive dynamics (max eigenvalue {rollup.max_eigenvalue} >= 1.0); refusing to roll up",
                evidence={"max_eigenvalue": rollup.max_eigenvalue},
                next_action=(
                    "Review endogenous time-series stationarity, lag specification, or deterministic "
                    "ridge regularization before interpreting the response"
                ),
            )

        raise DomainError(
            "LONG_TERM_UNCERTAINTY_REQUIRED",
            "The deterministic VARX prototype does not quantify posterior uncertainty; "
            "refusing to attach its point estimates to decision-grade provenance",
            evidence={
                "model_id": rollup.model_id,
                "diagnostic_status": rollup.diagnostic_status,
                "estimation_method": "ridge_regularized_least_squares",
                "uncertainty_quantified": False,
                "experimental": True,
            },
            next_action=(
                "Use a Bayesian long-term-effects implementation with posterior sampling, "
                "uncertainty intervals, and diagnostics before decision rollup"
            ),
        )
