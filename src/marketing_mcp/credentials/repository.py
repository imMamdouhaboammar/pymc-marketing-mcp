"""Credential repository protocol interface."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from marketing_mcp.credentials.models import CredentialAuditRecord, CredentialRecord


class CredentialRepository(Protocol):
    """Abstract storage for credentials and audit events."""

    def create(self, record: CredentialRecord) -> None: ...

    def get_by_id(self, credential_id: str) -> CredentialRecord | None: ...

    def find_active_by_prefix(self, prefix: str) -> Sequence[CredentialRecord]: ...

    def list_by_owner(self, tenant_id: str, owner_subject: str) -> Sequence[CredentialRecord]: ...

    def update_status(self, credential_id: str, status: str, revoked_at: str | None = None) -> CredentialRecord: ...

    def record_usage(self, credential_id: str, last_used_at: str) -> None: ...

    def append_audit_event(self, event: CredentialAuditRecord) -> None: ...

    def list_audit_events(self, tenant_id: str, limit: int = 100) -> Sequence[CredentialAuditRecord]: ...
