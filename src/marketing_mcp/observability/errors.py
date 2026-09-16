"""Error diagnostics registry and operator retrieval engine (Wave 6)."""

from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Any

from marketing_mcp.errors import NormalizedError


class ErrorDiagnosticRegistry:
    """Thread-safe bounded in-memory diagnostic ledger for operational error lookup."""

    def __init__(self, capacity: int = 1000, max_size: int | None = None) -> None:
        self.capacity = max_size if max_size is not None else capacity
        self._lock = Lock()
        self._entries: OrderedDict[str, NormalizedError] = OrderedDict()

    def record(self, err: NormalizedError) -> None:
        """Store a normalized error event in the bounded LRU registry."""
        with self._lock:
            if err.error_id in self._entries:
                del self._entries[err.error_id]
            elif len(self._entries) >= self.capacity:
                self._entries.popitem(last=False)
            self._entries[err.error_id] = err

    def lookup(self, error_id: str) -> dict[str, Any] | None:
        """Retrieve full technical diagnostic representation of an error by error_id."""
        with self._lock:
            err = self._entries.get(error_id)
            if err is None:
                return None
            return err.to_diagnostic_dict()

    def get_error(self, error_id: str) -> NormalizedError | None:
        """Retrieve the typed NormalizedError object by error_id."""
        with self._lock:
            return self._entries.get(error_id)

    def count(self) -> int:
        """Return the number of stored diagnostic errors."""
        with self._lock:
            return len(self._entries)

    def __len__(self) -> int:
        return self.count()

    def clear(self) -> None:
        """Clear all stored error diagnostics (used for testing)."""
        with self._lock:
            self._entries.clear()


GLOBAL_ERROR_REGISTRY = ErrorDiagnosticRegistry()


def record_error_diagnostic(err: NormalizedError) -> None:
    """Convenience helper to record a diagnostic error."""
    GLOBAL_ERROR_REGISTRY.record(err)


def get_error_diagnostic(error_id: str) -> dict[str, Any] | None:
    """Convenience helper to look up a diagnostic error by error_id."""
    return GLOBAL_ERROR_REGISTRY.lookup(error_id)


__all__ = [
    "ErrorDiagnosticRegistry",
    "GLOBAL_ERROR_REGISTRY",
    "get_error_diagnostic",
    "record_error_diagnostic",
]
