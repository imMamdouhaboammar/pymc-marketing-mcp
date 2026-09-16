"""Scope policy: catalog, tool mapping, and execution-time enforcement.

Authorization is enforced at tool execution (not only at the transport
boundary): every tool handler resolves its required scope via
:func:`scopes_for_tool` and calls :func:`require_scope` with the request's
principal.
"""

from __future__ import annotations

from marketing_mcp.errors import DomainError
from marketing_mcp.security.principal import Principal

SCOPE_CATALOG: frozenset[str] = frozenset(
    {
        "marketing:read",
        "marketing:model",
        "marketing:decide",
        "marketing:clv",
        "marketing:admin",
    }
)

WILDCARD_SCOPE = "*"

# Tool name -> scope. Tools not listed default to marketing:read.
TOOL_SCOPES: dict[str, str] = {
    # inspection / status / resources
    "get_model_status": "marketing:read",
    "get_channel_contributions": "marketing:read",
    "get_posterior_plots": "marketing:read",
    "inspect_dataset": "marketing:read",
    "list_datasets": "marketing:read",
    "validate_dataset": "marketing:read",
    "recommend_next_measurement": "marketing:read",
    # modeling lifecycle
    "register_dataset": "marketing:model",
    "fit_mmm": "marketing:model",
    "diagnose_mmm": "marketing:model",
    "calibrate_mmm": "marketing:model",
    "cross_validate_mmm": "marketing:model",
    "evaluate_prior_sensitivity": "marketing:model",
    "compare_models": "marketing:model",
    "select_best_model": "marketing:model",
    # budget decisions
    "simulate_budget": "marketing:decide",
    "optimize_budget": "marketing:decide",
    "optimize_flighting": "marketing:decide",
    "get_incremental_roas": "marketing:decide",
    "get_response_curves": "marketing:decide",
    # CLV
    "fit_purchase_model": "marketing:clv",
    "fit_value_model": "marketing:clv",
    "predict_expected_purchases": "marketing:clv",
    "predict_probability_alive": "marketing:clv",
    "predict_expected_spend": "marketing:clv",
    "estimate_customer_lifetime_value": "marketing:clv",
    "get_churn_risk_cohorts": "marketing:clv",
    # legacy wrappers follow their domain
    "fit_clv_model": "marketing:clv",
    "predict_customer_clv": "marketing:clv",
    # asynchronous jobs
    "submit_fit_mmm_job": "marketing:model",
    "get_job_status": "marketing:read",
    "cancel_job": "marketing:model",
    "list_jobs": "marketing:read",
    # administration
    "archive_model": "marketing:admin",
}

DEFAULT_TOOL_SCOPE = "marketing:read"


def all_scopes() -> frozenset[str]:
    """Every scope in the catalog — used for trusted local stdio principals."""
    return frozenset(SCOPE_CATALOG)


def scopes_for_tool(tool_name: str) -> tuple[str, ...]:
    """Required scopes for a tool. Returns a tuple for future multi-scope tools."""
    return (TOOL_SCOPES.get(tool_name, DEFAULT_TOOL_SCOPE),)


def require_scope(principal: Principal | None, scope: str) -> None:
    """Enforce that the principal may act under ``scope``.

    Raises:
        DomainError AUTH_REQUIRED: no principal supplied (protected context).
        DomainError INPUT_INVALID: unknown scope requested (catalog typo guard).
        DomainError AUTH_FORBIDDEN: authenticated caller lacks the scope.
    """
    if principal is None:
        raise DomainError(
            "AUTH_REQUIRED",
            "No authenticated principal; this operation requires authentication",
        )
    if scope not in SCOPE_CATALOG:
        raise DomainError(
            "INPUT_INVALID",
            f"Unknown scope '{scope}' requested",
            evidence={"requested": scope, "catalog": sorted(SCOPE_CATALOG)},
        )
    if WILDCARD_SCOPE in principal.scopes or scope in principal.scopes:
        return
    raise DomainError(
        "AUTH_FORBIDDEN",
        f"Principal '{principal.subject}' lacks required scope '{scope}'",
        evidence={"required_scope": scope},
        next_action="Request the missing scope from the authorization server",
    )
