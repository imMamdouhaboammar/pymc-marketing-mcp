"""MCP tool and API error boundary engine with telemetry and structured logging."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, Coroutine

from marketing_mcp.error_classifier import classify_exception
from marketing_mcp.errors import DomainError, NormalizedError
from marketing_mcp.mcp.context import get_current_execution_context
from marketing_mcp.observability.errors import GLOBAL_ERROR_REGISTRY
from marketing_mcp.observability.logging import current_request_id, current_tenant_id
from marketing_mcp.observability.metrics import GLOBAL_METRICS

logger = logging.getLogger("marketing_mcp.error_boundary")


def handle_exception_boundary(
    exc: BaseException,
    *,
    operation: str,
    component: str,
    stage: str | None = None,
    context: dict[str, Any] | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
    dataset_id: str | None = None,
    model_id: str | None = None,
    tenant_id: str | None = None,
    artifact_uri: str | None = None,
) -> NormalizedError:
    """Classify, log, meter, and record an exception into the diagnostic registry."""
    # Context resolution from context variables if not explicitly passed
    ctx_obj = get_current_execution_context()
    resolved_req_id = request_id or (ctx_obj.request_id if ctx_obj else None) or current_request_id.get()
    resolved_tenant_id = tenant_id or (
        ctx_obj.principal.tenant_id if ctx_obj and ctx_obj.principal else None
    ) or current_tenant_id.get()

    norm = classify_exception(
        exc,
        operation=operation,
        component=component,
        stage=stage,
        context=context,
        request_id=resolved_req_id,
        job_id=job_id,
        dataset_id=dataset_id,
        model_id=model_id,
        tenant_id=resolved_tenant_id,
        artifact_uri=artifact_uri,
    )

    # Record into diagnostic lookup registry
    GLOBAL_ERROR_REGISTRY.record(norm)

    # Record low-cardinality operational metrics
    tool_label = operation.split(":")[-1]
    GLOBAL_METRICS.increment_counter(
        "mcp_errors_total",
        labels={"code": norm.code, "category": norm.category, "tool": tool_label},
    )
    GLOBAL_METRICS.increment_counter(
        "mcp_operation_failures_total",
        labels={"operation": operation, "component": component},
    )
    if norm.retryable:
        GLOBAL_METRICS.increment_counter(
            "mcp_retryable_errors_total",
            labels={"code": norm.code},
        )

    # Structured logging with single authoritative log event
    diag = norm.to_diagnostic_dict()
    log_msg = f"MCP operation '{operation}' failed with {norm.code} ({norm.error_id}): {norm.message}"

    # Use error or warning depending on severity
    if norm.severity == "critical":
        logger.critical(log_msg, extra={"structured_data": diag})
    elif norm.severity == "warning" or norm.severity == "info":
        logger.warning(log_msg, extra={"structured_data": diag})
    else:
        # Include exception traceback for unexpected/internal errors
        include_exc = not isinstance(exc, DomainError)
        logger.error(log_msg, exc_info=include_exc, extra={"structured_data": diag})

    return norm


def mcp_error_boundary(
    operation: str,
    component: str = "MCPTool",
    stage: str | None = None,
) -> Callable[[Callable[..., Coroutine[Any, Any, Any]]], Callable[..., Coroutine[Any, Any, Any]]]:
    """Decorator wrapping an async MCP tool handler with canonical error normalization."""

    def decorator(fn: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Coroutine[Any, Any, Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except BaseException as exc:
                # Extract resource hints from arguments if present
                d_id = kwargs.get("dataset_id")
                m_id = kwargs.get("model_id")
                j_id = kwargs.get("job_id")

                # Handle Pydantic model inputs (e.g. config: FitMMMInput, input: CrossValidateMMMInput)
                if not d_id or not m_id:
                    for arg in list(args) + list(kwargs.values()):
                        if hasattr(arg, "dataset_id") and not d_id:
                            d_id = getattr(arg, "dataset_id", None)
                        if hasattr(arg, "model_id") and not m_id:
                            m_id = getattr(arg, "model_id", None)
                        if hasattr(arg, "job_id") and not j_id:
                            j_id = getattr(arg, "job_id", None)

                norm = handle_exception_boundary(
                    exc,
                    operation=operation,
                    component=component,
                    stage=stage,
                    dataset_id=str(d_id) if d_id else None,
                    model_id=str(m_id) if m_id else None,
                    job_id=str(j_id) if j_id else None,
                )
                return norm.to_mcp_response()

        return wrapper

    return decorator


__all__ = [
    "handle_exception_boundary",
    "mcp_error_boundary",
]
