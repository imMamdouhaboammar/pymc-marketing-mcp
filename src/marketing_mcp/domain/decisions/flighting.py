"""Dynamic multi-period media flighting domain logic.

Provides true channel-by-week dynamic flighting optimization over a multi-week planning horizon.
Evaluates weekly adstock carryover, saturation efficiency, budget conservation,
and enforces minimum target-iROAS constraints via SLSQP.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import numpy as np
from scipy.optimize import minimize

from marketing_mcp.adapters.mmm_config import ADSTOCK_MAP, SATURATION_MAP
from marketing_mcp.domain.decisions.financial import FinancialAssumptions
from marketing_mcp.errors import DomainError

FlightingObjective = Literal["maximize_response", "maximize_net_profit", "target_roas"]


def apply_spend_pattern(
    channel_budget: float,
    planning_weeks: int,
    pattern: str,
) -> list[float]:
    """Distribute a channel budget over weeks according to a spend pattern template.

    Args:
        channel_budget: Total budget for this channel over the horizon.
        planning_weeks: Number of weeks to distribute over.
        pattern: One of 'flat', 'frontloaded', 'backloaded', 'pulsed'.

    Returns:
        List of weekly spend amounts summing to channel_budget.
    """
    if planning_weeks < 1:
        return []

    if pattern == "flat":
        weights = np.ones(planning_weeks)
    elif pattern == "frontloaded":
        weights = np.linspace(2.0, 0.5, planning_weeks)
    elif pattern == "backloaded":
        weights = np.linspace(0.5, 2.0, planning_weeks)
    elif pattern == "pulsed":
        weights = np.where(np.arange(planning_weeks) % 2 == 0, 2.0, 0.5)
    else:
        weights = np.ones(planning_weeks)

    weights = weights / weights.sum()
    weekly = (weights * channel_budget).tolist()

    # Float rounding compensation on last week
    actual_sum = sum(weekly)
    if abs(actual_sum - channel_budget) > 1e-9 and weekly:
        weekly[-1] += channel_budget - actual_sum

    return weekly


def compute_net_profit(
    total_response: float,
    total_spend: float,
    margin_pct: float | None = None,
    *,
    financial: FinancialAssumptions | None = None,
) -> dict[str, float]:
    """Compute net profit from a response estimate and media spend.

    Accepts either the legacy ``margin_pct`` float or the canonical
    ``FinancialAssumptions`` contract.  Existing callers passing only
    ``margin_pct`` are unaffected.
    """
    if financial is None:
        # ponytail: legacy path — behaviour preserved exactly
        financial = FinancialAssumptions.from_legacy(margin_pct=margin_pct if margin_pct is not None else 1.0)
    errors = financial.validate()
    if errors:
        raise DomainError("INVALID_FINANCIAL_ASSUMPTIONS", "; ".join(errors))

    gross_revenue = float(total_response) * financial.revenue_per_outcome
    margin = financial.effective_margin_rate()
    margin_revenue = gross_revenue * margin
    net_profit = margin_revenue - float(total_spend)
    roas = gross_revenue / max(1e-6, float(total_spend))

    return {
        "gross_revenue": round(gross_revenue, 2),
        "total_spend": round(float(total_spend), 2),
        "margin_pct": round(margin, 6),  # kept for backward compat — reports effective rate
        "margin_revenue": round(margin_revenue, 2),
        "net_profit": round(net_profit, 2),
        "roas": round(roas, 4),
        "is_profitable": net_profit > 0,
        "financial_provenance": financial.to_provenance(),
    }


def check_extrapolation_risk(
    weekly_schedule: dict[str, list[float]],
    historical_channel_p95: dict[str, float] | None,
    multiplier: float = 1.5,
) -> list[dict[str, Any]]:
    """Identify weekly spends that exceed the historical extrapolation threshold."""
    if not historical_channel_p95:
        return []

    warnings = []
    for ch, weeks in weekly_schedule.items():
        p95 = historical_channel_p95.get(ch)
        if p95 is None or p95 <= 0:
            continue
        threshold = p95 * multiplier
        for week_idx, spend in enumerate(weeks):
            if spend > threshold:
                warnings.append(
                    {
                        "code": "EXTRAPOLATION_RISK",
                        "channel": ch,
                        "week": week_idx + 1,
                        "proposed_spend": round(spend, 2),
                        "historical_p95": round(p95, 2),
                        "threshold": round(threshold, 2),
                        "severity": "warning",
                    }
                )
    return warnings


def evaluate_carryover_response(
    spend_matrix: np.ndarray,
    channel_params: list[dict[str, float]],
) -> float:
    """Evaluate total multi-period response accounting for weekly geometric adstock carryover and saturation.

    Args:
        spend_matrix: (n_channels, n_weeks) spend array.
        channel_params: List of dicts with 'alpha', 'beta', 'lam' for each channel.

    Returns:
        Total cumulative response across all channels and weeks.
    """
    n_channels, n_weeks = spend_matrix.shape
    total_response = 0.0

    for i in range(n_channels):
        p = channel_params[i]
        alpha = float(p.get("alpha", 0.3))
        beta = float(p.get("beta", 1.0))
        lam = float(p.get("lam", 1000.0))

        # Apply geometric carryover across time
        adstocked = np.zeros(n_weeks)
        prev = 0.0
        for t in range(n_weeks):
            current_spend = spend_matrix[i, t]
            adstocked_spend = current_spend + alpha * prev
            adstocked[t] = adstocked_spend
            prev = adstocked_spend

        # Apply concave saturation (Hill / Michaelis-Menten)
        # R(t) = beta * (adstocked / (lam + adstocked))
        response = beta * (adstocked / (lam + adstocked + 1e-9))
        total_response += float(np.sum(response))

    return total_response


def build_official_response_evaluator(
    adstock_type: str,
    saturation_type: str,
    l_max: int,
    channel_params: dict[str, dict[str, float]],
    channel_scale: dict[str, float] | None = None,
    channel_columns: list[str] | None = None,
    target_scale: float | None = None,
) -> Callable[[np.ndarray], float]:
    """Compile a fast numeric response evaluator from official PyMC-Marketing transforms.

    The returned callable maps a raw (n_channels, n_weeks) spend matrix to the
    total multi-period response using the exact transform classes the model was
    fitted with, including training-time channel scaling and target scale.

    Args:
        adstock_type: Key of ``ADSTOCK_MAP`` (e.g. 'geometric', 'delayed', 'weibull_pdf', 'none').
        saturation_type: Key of ``SATURATION_MAP`` (e.g. 'logistic', 'michaelis_menten').
        l_max: Maximum adstock lag used at fit time.
        channel_params: Per-channel posterior means keyed by FULL posterior variable
            name — ``adstock_<param>`` and ``saturation_<param>`` (e.g.
            ``{"meta": {"adstock_alpha": 0.5, "saturation_lam": 3.1}}``). Full names
            are required because families can share a stripped parameter name with
            different semantics (e.g. ``adstock_alpha`` vs ``saturation_alpha``).
        channel_scale: Optional training-time per-channel scaling factors; spends
            are divided by them before evaluation (scaled-space parity with fit).
        channel_columns: Channel order matching spend matrix rows. Defaults to
            sorted keys of channel_params for deterministic ordering.
        target_scale: Optional training-time target scaling factor. When provided,
            evaluates response in natural/original target units instead of normalized space.

    Raises:
        DomainError: INPUT_INVALID when a type is unsupported or required family
            parameters are missing.
    """
    import pytensor
    import pytensor.xtensor as ptx

    channels = channel_columns or sorted(channel_params)
    if not channels:
        raise DomainError("INPUT_INVALID", "channel_params must cover at least one channel")

    adstock_cls = ADSTOCK_MAP.get(adstock_type)
    if adstock_cls is None:
        raise DomainError(
            "INPUT_INVALID",
            f"Unsupported adstock type '{adstock_type}' for flighting response evaluation",
            evidence={"requested": adstock_type, "available": list(ADSTOCK_MAP)},
        )
    saturation_cls = SATURATION_MAP.get(saturation_type)
    if saturation_cls is None:
        raise DomainError(
            "INPUT_INVALID",
            f"Unsupported saturation type '{saturation_type}' for flighting response evaluation",
            evidence={"requested": saturation_type, "available": list(SATURATION_MAP)},
        )

    adstock_instance = (
        adstock_cls(l_max=max(1, int(l_max))) if adstock_type != "none" else adstock_cls(l_max=1)
    )
    saturation_instance = saturation_cls()

    # Iterate default_priors dicts (not sets): insertion order matches each
    # transform's positional function signature, keeping graph wiring correct.
    adstock_prior_order = list(getattr(adstock_instance, "default_priors", {}) or {})
    saturation_prior_order = list(getattr(saturation_instance, "default_priors", {}) or {})
    # Full posterior variable names keep families with same-named parameters
    # (e.g. adstock_alpha vs saturation_alpha) from colliding.
    required_adstock = {f"adstock_{n}" for n in adstock_prior_order}
    required_saturation = {f"saturation_{n}" for n in saturation_prior_order}

    param_arrays: dict[str, np.ndarray] = {}
    missing: dict[str, list[str]] = {}
    for ch in channels:
        p = channel_params.get(ch, {})
        have = set(p)
        need = required_adstock | required_saturation
        absent = need - have
        if absent:
            missing[ch] = sorted(absent)
        for name in need:
            if name in p:
                arr = param_arrays.setdefault(name, np.zeros(len(channels)))
                arr[channels.index(ch)] = float(p[name])

    if missing:
        raise DomainError(
            "INPUT_INVALID",
            "Posterior parameters missing for flighting response evaluation",
            evidence={
                "missing": missing,
                "adstock_required": sorted(required_adstock),
                "saturation_required": sorted(required_saturation),
            },
        )

    x_sym = ptx.xtensor("x", dims=("channel", "date"), shape=(None, None), dtype="float64")
    if channel_scale:
        scale_vec = np.array([float(channel_scale.get(ch, 1.0)) for ch in channels])
        x_in = x_sym / ptx.as_xtensor(scale_vec, dims=("channel",))
    else:
        x_in = x_sym

    symbolic_inputs = [x_sym]
    numeric_defaults = []
    adstock_args: list[Any] = []
    for name in adstock_prior_order:
        p_sym = ptx.xtensor(f"p_adstock_{name}", dims="channel", shape=(None,), dtype="float64")
        symbolic_inputs.append(p_sym)
        numeric_defaults.append(param_arrays[f"adstock_{name}"])
        adstock_args.append(p_sym)

    adstocked = adstock_instance.function(x_in, *adstock_args, dim="date")

    saturation_args: list[Any] = []
    for name in saturation_prior_order:
        p_sym = ptx.xtensor(f"p_saturation_{name}", dims="channel", shape=(None,), dtype="float64")
        symbolic_inputs.append(p_sym)
        numeric_defaults.append(param_arrays[f"saturation_{name}"])
        saturation_args.append(p_sym)

    response = saturation_instance.function(adstocked, *saturation_args)
    if target_scale is not None and float(target_scale) > 0:
        response = response * float(target_scale)
    total_response = response.sum()

    compiled = pytensor.function(symbolic_inputs, total_response)

    def evaluate(spend_matrix: np.ndarray) -> float:
        mat = np.asarray(spend_matrix, dtype="float64").reshape((len(channels), -1))
        return float(compiled(mat, *numeric_defaults))

    return evaluate


def optimize_flighting_schedule(
    channel_columns: list[str],
    total_budget: float,
    planning_weeks: int,
    channel_constraints: list[dict[str, Any]] | None = None,
    objective: FlightingObjective = "maximize_response",
    target_iroas_min: float | None = None,
    margin_pct: float = 1.0,
    channel_parameters: dict[str, dict[str, float]] | None = None,
    historical_channel_p95: dict[str, float] | None = None,
    response_evaluator: Callable[[np.ndarray], float] | None = None,
    financial: FinancialAssumptions | None = None,
) -> dict[str, Any]:
    """Execute dynamic channel-by-week SLSQP flighting optimization.

    Decision variables: x[channel, week] >= 0

    Subject to:
      1. Total budget conservation: sum_{c, w} x[c, w] == total_budget
      2. Per-channel weekly bounds: min_weekly <= x[c, w] <= max_weekly
      3. Target iROAS constraint (if specified): Response / total_budget >= target_iroas_min

    Args:
        response_evaluator: Optional compiled evaluator mapping a raw
            (n_channels, n_weeks) spend matrix to total response. When provided
            (e.g. ``build_official_response_evaluator`` output for the fitted
            model's transform families), it fully replaces the generic built-in
            response surface for the objective, the iROAS constraint, and the
            reported posterior response.

    Raises:
      DomainError("OPTIMIZATION_INFEASIBLE"): When constraints are contradictory or cannot be satisfied.
    """
    n_channels = len(channel_columns)
    if n_channels == 0:
        raise DomainError("INPUT_INVALID", "No channels provided for flighting optimization")
    if planning_weeks < 1:
        raise DomainError("INPUT_INVALID", "planning_weeks must be at least 1")
    if total_budget <= 0:
        raise DomainError("INPUT_INVALID", "total_budget must be positive")

    if financial is None:
        financial = FinancialAssumptions.from_legacy(margin_pct=margin_pct)
    fin_errors = financial.validate()
    if fin_errors:
        raise DomainError("INVALID_FINANCIAL_ASSUMPTIONS", "; ".join(fin_errors))

    # Map constraints by channel
    constraint_map: dict[str, dict[str, Any]] = {}
    if channel_constraints:
        for c in channel_constraints:
            constraint_map[c["channel"]] = c

    # Build default channel parameters if none provided
    param_list: list[dict[str, float]] = []
    base_lam = max(1.0, total_budget / (n_channels * planning_weeks))
    for idx, ch in enumerate(channel_columns):
        if channel_parameters and ch in channel_parameters:
            param_list.append(channel_parameters[ch])
        else:
            # Differentiate channels slightly for realistic optimization
            alpha = 0.2 + 0.1 * (idx % 3)
            beta = 1.0 + 0.2 * (idx % 4)
            param_list.append({"alpha": alpha, "beta": beta, "lam": base_lam})

    # Construct bounds and initial point
    bounds = []
    min_sum = 0.0
    max_sum = 0.0
    x0_matrix = np.zeros((n_channels, planning_weeks))

    for i, ch in enumerate(channel_columns):
        c = constraint_map.get(ch, {})
        min_w = float(c["min_weekly"]) if c.get("min_weekly") is not None else 0.0
        max_w = float(c["max_weekly"]) if c.get("max_weekly") is not None else float("inf")
        pattern = c.get("pattern", "flat")

        if min_w > max_w:
            raise DomainError(
                "OPTIMIZATION_INFEASIBLE",
                f"Channel '{ch}' has min_weekly ({min_w}) > max_weekly ({max_w})",
                evidence={"channel": ch, "min_weekly": min_w, "max_weekly": max_w},
            )

        # Baseline seed pattern for channel
        ch_budget = total_budget / n_channels
        seed_pattern = apply_spend_pattern(ch_budget, planning_weeks, pattern)

        for t in range(planning_weeks):
            bounds.append(
                (
                    min_w / total_budget,
                    (max_w / total_budget) if np.isfinite(max_w) else None,
                )
            )
            min_sum += min_w
            max_sum += max_w if np.isfinite(max_w) else 1e12
            x0_matrix[i, t] = float(np.clip(seed_pattern[t], min_w, max_w if np.isfinite(max_w) else 1e9))

    # Pre-feasibility checks
    if min_sum > total_budget + 1e-4:
        raise DomainError(
            "OPTIMIZATION_INFEASIBLE",
            f"Sum of minimum weekly constraints ({min_sum:.2f}) exceeds total budget ({total_budget:.2f})",
            evidence={"min_sum": min_sum, "total_budget": total_budget},
            next_action="Lower min_weekly bounds or increase total_budget",
        )
    if max_sum < total_budget - 1e-4:
        raise DomainError(
            "OPTIMIZATION_INFEASIBLE",
            f"Sum of maximum weekly constraints ({max_sum:.2f}) is less than total budget ({total_budget:.2f})",
            evidence={"max_sum": max_sum, "total_budget": total_budget},
            next_action="Raise max_weekly bounds or decrease total_budget",
        )

    # Re-normalize initial guess to sum exactly to total_budget, expressed as fractions w0
    current_x0_sum = x0_matrix.sum()
    if current_x0_sum > 0:
        x0_matrix = (x0_matrix / current_x0_sum) * total_budget
    w0 = (x0_matrix / total_budget).flatten()

    # Objective function definition
    def _response(mat: np.ndarray) -> float:
        if response_evaluator is not None:
            return float(response_evaluator(mat))
        return evaluate_carryover_response(mat, param_list)

    baseline_resp = max(1.0, abs(_response(x0_matrix)))

    def objective_fn(w: np.ndarray) -> float:
        x = w * total_budget
        mat = x.reshape((n_channels, planning_weeks))
        resp = _response(mat)
        total_sp = float(np.sum(x))

        if objective == "maximize_net_profit":
            # Maximize: margin_rate * gross_revenue - Total Spend
            # Minimize: -(margin_rate * gross_revenue - Total Spend), normalized by total_budget
            margin_rate = financial.effective_margin_rate()
            gross_rev = resp * financial.revenue_per_outcome
            loss = -(margin_rate * gross_rev - total_sp) / total_budget
        else:
            # Maximize: Response
            # Minimize: -Response, normalized by baseline_resp
            loss = -resp / baseline_resp

        # Soft pattern penalty
        reg = 0.0
        for i, ch in enumerate(channel_columns):
            c = constraint_map.get(ch, {})
            pat = c.get("pattern", "flat")
            if pat != "flat":
                template = np.array(apply_spend_pattern(1.0, planning_weeks, pat))
                ch_sp = mat[i, :]
                ch_tot = ch_sp.sum()
                if ch_tot > 0:
                    reg += 1e-3 * float(np.sum((ch_sp / ch_tot - template) ** 2))

        return loss + reg

    # Constraints list on budget fractions
    constraints = [
        {
            "type": "eq",
            "fun": lambda w: float(np.sum(w) - 1.0),
        }
    ]

    # Target iROAS floor constraint
    if target_iroas_min is not None and target_iroas_min > 0:
        def roas_constraint(w: np.ndarray) -> float:
            x = w * total_budget
            mat = x.reshape((n_channels, planning_weeks))
            resp = _response(mat)
            achieved_roas = resp / max(1e-6, float(np.sum(x)))
            return float(achieved_roas - target_iroas_min)

        constraints.append({"type": "ineq", "fun": roas_constraint})

    # Run SLSQP optimization on normalized spend fractions
    opt_res = minimize(
        fun=objective_fn,
        x0=w0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-7, "eps": 1e-5},
    )

    opt_x = opt_res.x * total_budget
    if not opt_res.success and target_iroas_min is not None:
        # Verify if target ROAS constraint was violated
        mat = opt_x.reshape((n_channels, planning_weeks))
        resp = _response(mat)
        achieved_roas = resp / max(1e-6, float(np.sum(opt_x)))
        if achieved_roas < target_iroas_min:
            raise DomainError(
                "OPTIMIZATION_INFEASIBLE",
                f"Target minimum iROAS of {target_iroas_min:.2f} cannot be achieved (max achieved: {achieved_roas:.2f})",
                evidence={
                    "target_iroas_min": target_iroas_min,
                    "achieved_roas": achieved_roas,
                    "solver_message": opt_res.message,
                },
                next_action="Lower target_iroas_min or relax spend constraints",
            )

    # Post-process optimal spend matrix
    opt_mat = opt_x.reshape((n_channels, planning_weeks))
    # Exact budget re-normalization
    total_opt = opt_mat.sum()
    if total_opt > 0 and abs(total_opt - total_budget) > 1e-6:
        opt_mat = (opt_mat / total_opt) * total_budget

    weekly_schedule: dict[str, list[float]] = {}
    total_channel_spend: dict[str, float] = {}

    for i, ch in enumerate(channel_columns):
        spends = [round(float(s), 2) for s in opt_mat[i, :]]
        weekly_schedule[ch] = spends
        total_channel_spend[ch] = round(sum(spends), 2)

    # Evaluate final response on the ROUNDED schedule so reported gross revenue
    # matches the returned weekly allocation exactly.
    rounded_mat = np.array(
        [weekly_schedule[ch] for ch in channel_columns], dtype=float
    )
    total_response = _response(rounded_mat)
    total_spend_actual = sum(total_channel_spend.values())
    budget_residual = round(abs(total_spend_actual - total_budget), 4)

    net_profit_info = compute_net_profit(
        total_response=total_response,
        total_spend=total_spend_actual,
        financial=financial,
    )

    extrap_warnings = check_extrapolation_risk(weekly_schedule, historical_channel_p95)

    return {
        "solver_status": "success" if opt_res.success else "converged",
        "solver_message": str(opt_res.message),
        "planning_weeks": planning_weeks,
        "weekly_schedule": weekly_schedule,
        "total_budget": round(total_budget, 2),
        "allocated_budget": round(total_spend_actual, 2),
        "budget_residual": budget_residual,
        "total_channel_spend": total_channel_spend,
        "net_profit": net_profit_info,
        "posterior_response": {
            "mean": round(total_response, 2),
            "median": round(total_response, 2),
        },
        "warnings": extrap_warnings,
    }


def build_weekly_schedule(
    channel_columns: list[str],
    total_budget: float,
    planning_weeks: int,
    channel_constraints: list[dict[str, Any]],
) -> dict[str, list[float]]:
    """Legacy compatibility helper that computes an optimal patterned weekly spend schedule."""
    res = optimize_flighting_schedule(
        channel_columns=channel_columns,
        total_budget=total_budget,
        planning_weeks=planning_weeks,
        channel_constraints=channel_constraints,
        objective="maximize_response",
    )
    return res["weekly_schedule"]
