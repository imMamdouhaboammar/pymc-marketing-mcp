"""Operation tracking and cooperative cancellation guard for direct heavy operations."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
import threading
import uuid
from typing import Any

from marketing_mcp.errors import DomainError


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
    ) -> ActiveOperation:
        op_id = f"op_{op_type}_{uuid.uuid4().hex[:8]}"
        tenant_id = getattr(principal, "tenant_id", None) if principal else None
        owner = getattr(principal, "subject", "local") if principal else "local"
        now = datetime.now(UTC).isoformat()
        op = ActiveOperation(
            op_id=op_id,
            op_type=op_type,
            tenant_id=tenant_id,
            owner=owner,
            started_at=now,
            details=details or {},
        )
        with self._lock:
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
    ):
        """Context manager that wraps an async call and cancels the underlying thread if cancelled."""
        op = self.register_operation(op_type, principal, details)
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
