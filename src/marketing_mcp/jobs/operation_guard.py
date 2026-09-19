"""Operation tracking and cooperative cancellation guard for direct heavy operations."""

from __future__ import annotations

import asyncio
import hashlib
import json
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def canonical_operation_identity(
    op_type: str,
    principal: Any = None,
    payload: Any = None,
) -> str:
    """Compute deterministic SHA-256 operation identity scoped by tenant and semantic payload.

    Guarantees:
    1. Tenant isolation: different tenant/principal scopes yield different identities.
    2. Semantic sensitivity: different configs/payloads on the same resource yield different identities.
    3. Canonical representation: dict key ordering does not affect the identity.
    4. Deterministic string output: 'op_ident_<op_type>_<hash[:16]>'.
    """
    tenant_id = getattr(principal, "tenant_id", None) if principal else None
    owner = getattr(principal, "subject", "local") if principal else "local"

    def _normalize(val: Any) -> Any:
        if hasattr(val, "model_dump"):
            return _normalize(val.model_dump(mode="json"))
        elif isinstance(val, dict):
            return {k: _normalize(v) for k, v in sorted(val.items(), key=lambda item: str(item[0]))}
        elif isinstance(val, (list, tuple)):
            return [_normalize(item) for item in val]
        elif isinstance(val, (set, frozenset)):
            return sorted([_normalize(item) for item in val], key=str)
        elif isinstance(val, (int, float, str, bool)) or val is None:
            return val
        else:
            return str(val)

    envelope = {
        "op_type": op_type,
        "tenant_id": str(tenant_id or "default"),
        "owner": str(owner or "anonymous"),
        "payload": _normalize(payload),
    }
    canonical_bytes = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()[:16]
    return f"op_ident_{op_type}_{digest}"


@dataclass
class ActiveOperation:
    op_id: str
    op_type: str
    tenant_id: str | None
    owner: str | None
    started_at: str
    cancel_event: threading.Event = field(default_factory=threading.Event)
    status: str = "running"
    details: dict[str, Any] = field(default_factory=dict)

    def cancel(self) -> None:
        self.status = "cancelled"
        self.cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()


class ConcurrencyCancellationGuard:
    """Tracks active direct operations and coordinates cooperative cancellation."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active: dict[str, ActiveOperation] = {}
        self._history: list[ActiveOperation] = []

    def register_operation(
        self,
        op_type: str,
        principal: Any = None,
        details: dict[str, Any] | None = None,
        identity_key: str | None = None,
    ) -> ActiveOperation:
        from marketing_mcp.errors import DomainError

        ident = (
            identity_key
            or (details.get("identity_key") if details else None)
            or (details.get("idempotency_key") if details else None)
        )
        tenant_id = getattr(principal, "tenant_id", None) if principal else None
        owner = getattr(principal, "subject", "local") if principal else "local"
        now = datetime.now(UTC).isoformat()
        effective_details = dict(details or {})
        if ident:
            effective_details["identity_key"] = ident

        with self._lock:
            if ident:
                for active_op in self._active.values():
                    if active_op.details.get("identity_key") == ident:
                        raise DomainError(
                            "OPERATION_ALREADY_RUNNING",
                            f"An operation with identity '{ident}' is currently active",
                            evidence={
                                "op_id": active_op.op_id,
                                "op_type": active_op.op_type,
                                "status": active_op.status,
                            },
                            next_action="Wait for the active operation to complete or check its status.",
                        )
            op_id = f"op_{op_type}_{uuid.uuid4().hex[:8]}"
            op = ActiveOperation(
                op_id=op_id,
                op_type=op_type,
                tenant_id=tenant_id,
                owner=owner,
                started_at=now,
                details=effective_details,
            )
            self._active[op_id] = op
            return op

    def unregister_operation(self, op_id: str) -> None:
        with self._lock:
            op = self._active.pop(op_id, None)
            if op:
                self._history.append(op)
                if len(self._history) > 100:
                    self._history = self._history[-100:]

    def get_active(self, op_id: str) -> ActiveOperation | None:
        with self._lock:
            return self._active.get(op_id)

    def list_active(self, tenant_id: str | None = None) -> list[ActiveOperation]:
        with self._lock:
            ops = list(self._active.values())
        if tenant_id:
            ops = [op for op in ops if op.tenant_id == tenant_id]
        return ops

    @asynccontextmanager
    async def track(
        self,
        op_type: str,
        principal: Any = None,
        details: dict[str, Any] | None = None,
        identity_key: str | None = None,
    ):
        """Context manager that wraps an async call and cancels the underlying thread if cancelled."""
        op = self.register_operation(op_type, principal, details, identity_key=identity_key)
        try:
            yield op
            if not op.is_cancelled:
                op.status = "completed"
        except asyncio.CancelledError:
            op.cancel()
            raise
        except Exception:
            if not op.is_cancelled:
                op.status = "failed"
            raise
        finally:
            self.unregister_operation(op.op_id)

    async def run_tracked_executor(
        self,
        op_type: str,
        func: Any,
        principal: Any = None,
        details: dict[str, Any] | None = None,
        identity_key: str | None = None,
    ) -> Any:
        """Execute a blocking function in an executor thread with completion-bound tracking.

        Unlike request-lifetime-bound tracking, the operation remains registered in
        _active until the underlying executor thread actually terminates, preventing
        overlapping duplicate retries under the same identity while compute is unwinding.
        """
        op = self.register_operation(
            op_type=op_type,
            principal=principal,
            details=details,
            identity_key=identity_key,
        )
        loop = asyncio.get_running_loop()

        result_holder: list[Any] = []
        error_holder: list[BaseException] = []

        def _worker_wrapper() -> None:
            try:
                res = func(op.cancel_event)
                result_holder.append(res)
                if not op.is_cancelled:
                    op.status = "completed"
            except BaseException as ex:
                error_holder.append(ex)
                if not op.is_cancelled:
                    op.status = "failed"
            finally:
                self.unregister_operation(op.op_id)

        future = loop.run_in_executor(None, _worker_wrapper)
        try:
            await asyncio.shield(future)
            if error_holder:
                raise error_holder[0]
            return result_holder[0] if result_holder else None
        except asyncio.CancelledError:
            op.cancel()
            raise
