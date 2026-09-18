"""Bayesian VAR Long-Term Brand Effects prototype engine (T8 - Experimental)."""

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


class BayesianVARLongTermEngine(LongTermEffectsEngine):
    """Bayesian VAR engine for estimating long-term brand equity multipliers.

    Marked as EXPERIMENTAL in platform capabilities.
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

        # Extract numeric matrices
        for col in endogenous_columns + exogenous_channels:
            if col not in df.columns:
                raise DomainError("INPUT_INVALID", f"Column '{col}' not found in dataset")

        y_raw = df[endogenous_columns].apply(pd.to_numeric, errors="coerce").dropna().to_numpy(dtype=float)
        x_raw = df[exogenous_channels].apply(pd.to_numeric, errors="coerce").dropna().to_numpy(dtype=float)

        min_len = min(len(y_raw), len(x_raw))
        if min_len < 16:
            raise DomainError(
                "DATASET_TOO_SHORT",
                f"Dataset length ({min_len}) is too short for VAR identification (minimum 16 periods required)",
            )

        y = y_raw[:min_len]
        x = x_raw[:min_len]

        # Time series alignment for VAR(1): Y_t against Y_{t-1} and X_t
        y_curr = y[1:]  # shape: (T-1, m_endo)
        y_lag = y[:-1]  # shape: (T-1, m_endo)
        x_curr = x[1:]  # shape: (T-1, k_exo)
        t_obs = len(y_curr)

        # Regressors matrix Z = [Y_lag, X_curr, 1]
        ones = np.ones((t_obs, 1))
        z = np.hstack([y_lag, x_curr, ones])

        # Ridge / Minnesota shrinkage regularization to ensure well-conditioned inversion
        ridge_diag = np.ones(z.shape[1]) * 1e-4
        # Slightly higher shrinkage on lag cross-terms
        ridge_diag[:m_endo] = 1e-2
        reg_matrix = np.diag(ridge_diag)

        # OLS / Bayesian posterior mode coefficients: Beta = (Z'Z + Lambda)^(-1) Z'Y
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

            initial_val = max(1e-6, abs(resp_h[0]))
            cum_val = float(sum(resp_h))
            mult = max(1.0, round(cum_val / initial_val, 3)) if is_stationary else 1.0

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
                "engine": "BayesianVARLongTermEngine",
                "horizon": horizon,
                "experimental": True,
            },
        )

    def rollup_into_decision(
        self,
        decision_result: dict[str, Any],
        rollup: LongTermRollup,
    ) -> dict[str, Any]:
        """Attach long-term brand multipliers to an MMM decision result."""
        if rollup.diagnostic_status == "rejected":
            raise DomainError(
                "LONG_TERM_GATE_REJECTED",
                f"Long-term VAR model has non-stationary explosive dynamics (max eigenvalue {rollup.max_eigenvalue} >= 1.0); refusing to roll up",
                evidence={"max_eigenvalue": rollup.max_eigenvalue},
                next_action="Review endogenous time series stationarity or regularize VAR lag priors",
            )

        enriched = dict(decision_result)
        prov = enriched.setdefault("provenance", {})
        prov["long_term_effects"] = {
            "var_model_id": rollup.model_id,
            "status": rollup.diagnostic_status,
            "channel_multipliers": rollup.channel_multipliers,
            "max_eigenvalue": rollup.max_eigenvalue,
            "experimental": True,
        }
        return enriched
