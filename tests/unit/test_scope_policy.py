"""Scope policy contract tests (Wave 3 Task 2).

Policy:
- Principals carry an auth_type and a frozenset of scopes.
- Local stdio principals are implicitly trusted: they hold every scope
  (wildcard) so local workflows never hit authorization friction.
- OAuth principals hold only their granted scopes; API-key principals hold the
  explicitly configured private-mode scopes.
- A missing principal is always rejected in protected contexts (AUTH_REQUIRED).
- An authenticated principal lacking the required scope is rejected
  (AUTH_FORBIDDEN): marketing:read can never drive decision tools.
"""

from __future__ import annotations

import pytest

from marketing_mcp.errors import DomainError
from marketing_mcp.security.policy import (
    SCOPE_CATALOG,
    all_scopes,
    require_scope,
    scopes_for_tool,
)
from marketing_mcp.security.principal import Principal


def _principal(auth_type: str, scopes) -> Principal:
    return Principal(subject="u1", auth_type=auth_type, scopes=frozenset(scopes))  # type: ignore[arg-type]


class TestPrincipalModel:
    def test_oauth_principal_with_explicit_scopes(self):
        p = _principal("oauth", ["marketing:read"])
        assert p.subject == "u1"
        assert p.scopes == frozenset(["marketing:read"])
        assert p.auth_type == "oauth"

    def test_tenant_id_optional(self):
        p = _principal("api_key", [])
        assert p.tenant_id is None


class TestRequireScope:
    def test_missing_principal_rejected_auth_required(self):
        with pytest.raises(DomainError) as exc_info:
            require_scope(None, "marketing:read")
        assert exc_info.value.code == "AUTH_REQUIRED"

    def test_scope_present_passes(self):
        p = _principal("oauth", ["marketing:read", "marketing:model"])
        require_scope(p, "marketing:read")

    def test_scope_missing_rejected_auth_forbidden(self):
        p = _principal("oauth", ["marketing:read"])
        with pytest.raises(DomainError) as exc_info:
            require_scope(p, "marketing:decide")
        assert exc_info.value.code == "AUTH_FORBIDDEN"

    def test_read_cannot_call_decision_tools(self):
        p = _principal("oauth", ["marketing:read"])
        with pytest.raises(DomainError) as exc_info:
            require_scope(p, "marketing:decide")
        assert exc_info.value.code == "AUTH_FORBIDDEN"

    def test_stdio_local_wildcard_holds_every_scope(self):
        p = _principal("stdio", all_scopes())
        for scope in SCOPE_CATALOG:
            require_scope(p, scope)

    def test_wildcard_token_grants_everything_but_only_via_explicit_config(self):
        p = _principal("api_key", ["*"])
        for scope in SCOPE_CATALOG:
            require_scope(p, scope)

    def test_unknown_scope_refused_even_from_wildcard(self):
        p = _principal("oauth", ["*"])
        with pytest.raises(DomainError) as exc_info:
            require_scope(p, "marketing:nonexistent")
        assert exc_info.value.code == "INPUT_INVALID"


class TestScopeMap:
    def test_catalog_contains_the_five_initial_scopes(self):
        assert set(SCOPE_CATALOG) == {
            "marketing:read",
            "marketing:model",
            "marketing:decide",
            "marketing:clv",
            "marketing:admin",
        }

    def test_decision_tools_map_to_marketing_decide(self):
        for tool in ("simulate_budget", "optimize_budget", "optimize_flighting"):
            assert scopes_for_tool(tool)[0] == "marketing:decide"

    def test_modeling_tools_map_to_marketing_model(self):
        for tool in ("fit_mmm", "diagnose_mmm", "calibrate_mmm", "compare_models"):
            assert scopes_for_tool(tool)[0] == "marketing:model"

    def test_inspection_tools_map_to_marketing_read(self):
        for tool in ("get_model_status", "get_channel_contributions"):
            assert scopes_for_tool(tool)[0] == "marketing:read"

    def test_clv_tools_map_to_marketing_clv(self):
        for tool in ("fit_purchase_model", "predict_expected_purchases"):
            assert scopes_for_tool(tool)[0] == "marketing:clv"

    def test_admin_tools_map_to_marketing_admin(self):
        assert scopes_for_tool("archive_model")[0] == "marketing:admin"
