"""Credential service implementing secure API key issuance, verification, and revocation."""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from marketing_mcp.credentials.models import (
    CredentialAuditRecord,
    CredentialRecord,
    IssuedCredential,
)
from marketing_mcp.credentials.repository import CredentialRepository
from marketing_mcp.errors import DomainError
from marketing_mcp.security.policy import SCOPE_CATALOG
from marketing_mcp.security.principal import Principal

SECRET_PREFIX = "mcp_live_"
PREFIX_LENGTH = 16


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_secret(secret: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{secret}".encode()).hexdigest()


class CredentialService:
    """Business logic for issuing, verifying, and revoking API keys."""

    def __init__(self, repository: CredentialRepository):
        self.repository = repository

    def issue(
        self,
        *,
        tenant_id: str,
        owner_subject: str,
        name: str,
        scopes: Sequence[str] | frozenset[str],
        actor_principal: Principal | None = None,
    ) -> IssuedCredential:
        """Issue a new API key. The raw secret is returned exactly once."""
        validated_scopes = frozenset(scopes)
        for s in validated_scopes:
            if s != "*" and s not in SCOPE_CATALOG:
                raise DomainError("INPUT_INVALID", f"Invalid scope '{s}' requested for credential")

        # Security check: actor cannot grant scopes they do not have unless admin
        if actor_principal is not None and "*" not in actor_principal.scopes and "marketing:admin" not in actor_principal.scopes:
            for s in validated_scopes:
                if s not in actor_principal.scopes:
                    raise DomainError(
                        "AUTH_FORBIDDEN",
                        f"Cannot grant scope '{s}' not held by caller",
                        evidence={"requested": s, "held": list(actor_principal.scopes)},
                    )

        raw_random = secrets.token_urlsafe(32)
        secret = f"{SECRET_PREFIX}{raw_random}"
        prefix = secret[:PREFIX_LENGTH]
        salt = secrets.token_hex(16)
        verifier = _hash_secret(secret, salt)

        cred_id = f"cred_{uuid.uuid4().hex[:12]}"
        now = _utc_now()

        record = CredentialRecord(
            credential_id=cred_id,
            tenant_id=tenant_id,
            owner_subject=owner_subject,
            name=name,
            prefix=prefix,
            verifier=verifier,
            salt=salt,
            scopes=validated_scopes,
            status="active",
            created_at=now,
        )

        self.repository.create(record)

        # Audit log
        self.repository.append_audit_event(
            CredentialAuditRecord(
                event_id=f"audit_{uuid.uuid4().hex[:12]}",
                event_type="created",
                tenant_id=tenant_id,
                actor_subject=actor_principal.subject if actor_principal else owner_subject,
                timestamp=now,
                credential_id=cred_id,
                prefix=prefix,
                details={"name": name, "scopes": list(validated_scopes)},
            )
        )

        return IssuedCredential(record=record, secret=secret)

    def verify(self, secret: str) -> CredentialRecord | None:
        """Verify an incoming API key secret in constant time. Returns active record or None."""
        if not secret or not secret.startswith(SECRET_PREFIX) or len(secret) < PREFIX_LENGTH:
            return None

        prefix = secret[:PREFIX_LENGTH]
        candidates = self.repository.find_active_by_prefix(prefix)
        matched_record: CredentialRecord | None = None

        for cand in candidates:
            if cand.status != "active":
                continue
            expected_verifier = _hash_secret(secret, cand.salt)
            if hmac.compare_digest(cand.verifier, expected_verifier):
                matched_record = cand
                break

        now = _utc_now()
        if matched_record is not None:
            self.repository.record_usage(matched_record.credential_id, now)
            self.repository.append_audit_event(
                CredentialAuditRecord(
                    event_id=f"audit_{uuid.uuid4().hex[:12]}",
                    event_type="used",
                    tenant_id=matched_record.tenant_id,
                    actor_subject=matched_record.owner_subject,
                    timestamp=now,
                    credential_id=matched_record.credential_id,
                    prefix=matched_record.prefix,
                )
            )
            return dataclasses.replace(matched_record, last_used_at=now)

        # Failed verification audit
        self.repository.append_audit_event(
            CredentialAuditRecord(
                event_id=f"audit_{uuid.uuid4().hex[:12]}",
                event_type="auth_failed",
                tenant_id="unknown",
                actor_subject="anonymous",
                timestamp=now,
                prefix=prefix,
            )
        )
        return None

    def revoke(self, credential_id: str, actor_principal: Principal) -> CredentialRecord:
        """Revoke an existing credential."""
        record = self.repository.get_by_id(credential_id)
        if record is None:
            raise DomainError("CREDENTIAL_NOT_FOUND", f"Credential '{credential_id}' was not found")

        # Authorization: must be in same tenant and be owner or admin
        if record.tenant_id != actor_principal.tenant_id and actor_principal.auth_type != "stdio":
            raise DomainError(
                "AUTH_FORBIDDEN",
                f"Access denied to credential belonging to tenant '{record.tenant_id}'",
            )

        is_admin = "*" in actor_principal.scopes or "marketing:admin" in actor_principal.scopes
        if record.owner_subject != actor_principal.subject and not is_admin and actor_principal.auth_type != "stdio":
            raise DomainError(
                "AUTH_FORBIDDEN",
                f"Principal '{actor_principal.subject}' is not authorized to revoke credential owned by '{record.owner_subject}'",
            )

        now = _utc_now()
        updated = self.repository.update_status(credential_id, status="revoked", revoked_at=now)

        self.repository.append_audit_event(
            CredentialAuditRecord(
                event_id=f"audit_{uuid.uuid4().hex[:12]}",
                event_type="revoked",
                tenant_id=record.tenant_id,
                actor_subject=actor_principal.subject,
                timestamp=now,
                credential_id=credential_id,
                prefix=record.prefix,
                details={"revoked_by": actor_principal.subject},
            )
        )
        return updated

    def list_for_owner(self, tenant_id: str, owner_subject: str) -> Sequence[CredentialRecord]:
        """List credentials for a specific tenant and owner."""
        return self.repository.list_by_owner(tenant_id, owner_subject)


__all__ = ["CredentialService"]
