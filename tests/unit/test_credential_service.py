"""Unit tests for CredentialService and SQLiteCredentialRepository."""

from __future__ import annotations

from pathlib import Path

import pytest

from marketing_mcp.credentials.service import CredentialService
from marketing_mcp.credentials.sqlite_repository import SQLiteCredentialRepository
from marketing_mcp.errors import DomainError
from marketing_mcp.security.principal import Principal


@pytest.fixture
def credential_service(tmp_path: Path):
    repo = SQLiteCredentialRepository(tmp_path / "credentials.db")
    return CredentialService(repo)


def test_credential_issue_and_verify(credential_service: CredentialService):
    issued = credential_service.issue(
        tenant_id="tenant_alpha",
        owner_subject="user_alice",
        name="Production Key",
        scopes=["marketing:read", "marketing:model"],
    )

    assert issued.secret.startswith("mcp_live_")
    assert issued.record.tenant_id == "tenant_alpha"
    assert issued.record.owner_subject == "user_alice"
    assert issued.record.status == "active"
    assert issued.record.verifier != issued.secret
    assert issued.record.salt

    # 1. Verification with valid secret succeeds
    verified = credential_service.verify(issued.secret)
    assert verified is not None
    assert verified.credential_id == issued.record.credential_id
    assert verified.tenant_id == "tenant_alpha"
    assert verified.scopes == frozenset(["marketing:read", "marketing:model"])
    assert verified.last_used_at is not None

    # 2. Verification with invalid secret fails
    assert credential_service.verify("mcp_live_invalid_secret_key_123456789") is None
    assert credential_service.verify("") is None
    assert credential_service.verify("invalid_prefix_secret") is None


def test_credential_revocation_prevents_verification(credential_service: CredentialService):
    issued = credential_service.issue(
        tenant_id="tenant_alpha",
        owner_subject="user_alice",
        name="Key to Revoke",
        scopes=["marketing:read"],
    )

    # Active key works
    assert credential_service.verify(issued.secret) is not None

    # Revoke by owner
    principal_alice = Principal(
        subject="user_alice",
        auth_type="oauth",
        tenant_id="tenant_alpha",
        scopes=frozenset(["marketing:read"]),
    )
    revoked = credential_service.revoke(issued.record.credential_id, principal_alice)
    assert revoked.status == "revoked"
    assert revoked.revoked_at is not None

    # Revoked key fails verification immediately
    assert credential_service.verify(issued.secret) is None


def test_credential_revocation_unauthorized_denied(credential_service: CredentialService):
    issued = credential_service.issue(
        tenant_id="tenant_alpha",
        owner_subject="user_alice",
        name="Alice Key",
        scopes=["marketing:read"],
    )

    # Bob (different user in same tenant, non-admin) cannot revoke
    principal_bob = Principal(
        subject="user_bob",
        auth_type="oauth",
        tenant_id="tenant_alpha",
        scopes=frozenset(["marketing:read"]),
    )
    with pytest.raises(DomainError) as exc_info:
        credential_service.revoke(issued.record.credential_id, principal_bob)
    assert exc_info.value.code == "AUTH_FORBIDDEN"

    # User in different tenant cannot revoke
    principal_charlie = Principal(
        subject="user_charlie",
        auth_type="oauth",
        tenant_id="tenant_beta",
        scopes=frozenset(["marketing:admin"]),
    )
    with pytest.raises(DomainError) as exc_info:
        credential_service.revoke(issued.record.credential_id, principal_charlie)
    assert exc_info.value.code == "AUTH_FORBIDDEN"


def test_credential_listing_and_audit(credential_service: CredentialService):
    credential_service.issue(
        tenant_id="tenant_alpha",
        owner_subject="user_alice",
        name="Key 1",
        scopes=["marketing:read"],
    )
    credential_service.issue(
        tenant_id="tenant_alpha",
        owner_subject="user_alice",
        name="Key 2",
        scopes=["marketing:decide"],
    )

    keys = credential_service.list_for_owner("tenant_alpha", "user_alice")
    assert len(keys) == 2
    for k in keys:
        public_view = k.to_public_dict()
        assert "secret" not in public_view
        assert "verifier" not in public_view
        assert "salt" not in public_view
        assert public_view["name"] in ("Key 1", "Key 2")

    # Verify audit events
    audit_events = credential_service.repository.list_audit_events("tenant_alpha")
    assert len(audit_events) >= 2
    event_types = {e.event_type for e in audit_events}
    assert "created" in event_types
