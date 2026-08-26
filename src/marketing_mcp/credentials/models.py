"""Credential domain models for backend-controlled API key management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class CredentialRecord:
    credential_id: str
    tenant_id: str
    owner_subject: str
    name: str
    prefix: str
    verifier: str
    salt: str
    scopes: frozenset[str]
    status: Literal["active", "revoked"] = "active"
    created_at: str = ""
    revoked_at: str | None = None
    last_used_at: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """Public view safe to return to UI/clients — NEVER contains secret or verifier."""
        return {
            "credential_id": self.credential_id,
            "tenant_id": self.tenant_id,
            "owner_subject": self.owner_subject,
            "name": self.name,
            "prefix": self.prefix,
            "scopes": sorted(self.scopes),
            "status": self.status,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
            "last_used_at": self.last_used_at,
        }


@dataclass(frozen=True)
class IssuedCredential:
    record: CredentialRecord
    secret: str


@dataclass(frozen=True)
class CredentialAuditRecord:
    event_id: str
    event_type: Literal["created", "used", "revoked", "auth_failed"]
    tenant_id: str
    actor_subject: str
    timestamp: str
    credential_id: str | None = None
    prefix: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
