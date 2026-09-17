"""Exception classification and cause chain extraction engine."""

from __future__ import annotations

import sqlite3
import traceback
import urllib.error
from typing import Any

from pydantic import ValidationError

from marketing_mcp.errors import (
    DomainError,
    ErrorCategory,
    ErrorSeverity,
    NormalizedError,
    OriginalErrorInfo,
    generate_error_id,
    get_error_definition,
)


def extract_cause_chain(exc: BaseException, max_depth: int = 10) -> list[OriginalErrorInfo]:
    """Walk Python exception causes and contexts to extract a structured chain."""
    causes: list[OriginalErrorInfo] = []
    current: BaseException | None = getattr(exc, "__cause__", None) or getattr(exc, "__context__", None)
    depth = 0

    while current is not None and depth < max_depth:
        module_name = getattr(type(current), "__module__", None)
        status_code = getattr(current, "code", getattr(current, "status_code", getattr(current, "status", None)))
        causes.append(
            OriginalErrorInfo(
                type=type(current).__name__,
                module=module_name,
                message=str(current),
                code=status_code if isinstance(status_code, (int, str)) else None,
            )
        )
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
        depth += 1

    return causes


def classify_exception(
    exc: BaseException,
    *,
    operation: str | None = None,
    component: str | None = None,
    stage: str | None = None,
    context: dict[str, Any] | None = None,
    request_id: str | None = None,
    job_id: str | None = None,
    dataset_id: str | None = None,
    model_id: str | None = None,
    tenant_id: str | None = None,
    artifact_uri: str | None = None,
) -> NormalizedError:
    """Classify any exception into a canonical NormalizedError with diagnostics and cause chain."""
    error_id = generate_error_id()
    ctx = dict(context or {})
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc.__traceback__ else None

    # 1. DomainError: already has code and semantics
    if isinstance(exc, DomainError):
        norm = exc.to_normalized()
        # Merge invocation context
        merged_context = dict(norm.context)
        merged_context.update(ctx)

        # Retain stack trace
        norm.stack_trace = tb_str
        norm.operation = operation or norm.operation
        norm.component = component or norm.component
        norm.stage = stage or norm.stage
        norm.request_id = request_id or norm.request_id
        norm.job_id = job_id or norm.job_id
        norm.dataset_id = dataset_id or norm.dataset_id
        norm.model_id = model_id or norm.model_id
        norm.tenant_id = tenant_id or norm.tenant_id
        norm.artifact_uri = artifact_uri or norm.artifact_uri
        norm.context = merged_context

        if not norm.cause_chain:
            norm.cause_chain = extract_cause_chain(exc)

        return norm

    # Extract original error details for upstream exceptions
    module_name = getattr(type(exc), "__module__", None)
    err_code = getattr(exc, "code", getattr(exc, "status_code", getattr(exc, "status", None)))
    numeric_or_str_code = err_code if isinstance(err_code, (int, str)) else None

    original_error = OriginalErrorInfo(
        type=type(exc).__name__,
        module=module_name,
        message=str(exc),
        code=numeric_or_str_code,
    )
    cause_chain = extract_cause_chain(exc)

    # 2. Pydantic ValidationError
    if isinstance(exc, ValidationError):
        defn = get_error_definition("INPUT_INVALID")
        evidence = {
            "validation_errors": [
                {
                    "loc": list(err.get("loc", ())),
                    "msg": err.get("msg", ""),
                    "type": err.get("type", ""),
                }
                for err in exc.errors()[:10]
            ]
        }
        return NormalizedError(
            error_id=error_id,
            code=defn.code,
            category=defn.category.value,
            severity=defn.severity.value,
            message="Input validation failed",
            user_message="Input validation failed for the requested operation",
            operation=operation,
            component=component,
            stage=stage or "validation",
            retryable=False,
            user_actionable=True,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            evidence=evidence,
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    # 3. User input errors (KeyError, ValueError)
    if isinstance(exc, (KeyError, ValueError)):
        defn = get_error_definition("INVALID_ARGUMENT")
        return NormalizedError(
            error_id=error_id,
            code=defn.code,
            category=defn.category.value,
            severity=defn.severity.value,
            message=str(exc) or "Invalid input parameter or missing key",
            user_message=f"Invalid argument: {exc}",
            operation=operation,
            component=component,
            stage=stage or "validation",
            retryable=False,
            user_actionable=True,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            evidence={"error_type": type(exc).__name__, "detail": str(exc)},
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    # 4. SQLite exceptions
    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        is_busy = "locked" in msg or "busy" in msg or "timeout" in msg
        is_read_op = operation and any(r in operation.lower() for r in ("get", "list", "read", "load", "find"))
        code = "PERSISTENCE_READ_FAILED" if is_read_op else "PERSISTENCE_WRITE_FAILED"
        defn = get_error_definition(code)
        return NormalizedError(
            error_id=error_id,
            code=code,
            category=ErrorCategory.PERSISTENCE.value,
            severity=ErrorSeverity.ERROR.value,
            message="Persistence operational failure occurred during database execution",
            operation=operation,
            component=component or "SQLiteRepository",
            stage=stage or "persistence",
            retryable=is_busy or defn.retryable,
            user_actionable=False,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            evidence={"database_error": str(exc)},
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    if isinstance(exc, sqlite3.IntegrityError):
        defn = get_error_definition("PERSISTENCE_WRITE_FAILED")
        return NormalizedError(
            error_id=error_id,
            code="PERSISTENCE_WRITE_FAILED",
            category=ErrorCategory.PERSISTENCE.value,
            severity=ErrorSeverity.ERROR.value,
            message="Database integrity or constraint violation",
            operation=operation,
            component=component or "SQLiteRepository",
            stage=stage or "persistence",
            retryable=False,
            user_actionable=False,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            evidence={"integrity_error": str(exc)},
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    # 4. HTTP and network errors
    if isinstance(exc, urllib.error.HTTPError):
        is_transient = exc.code in (429, 500, 502, 503, 504)
        defn = get_error_definition("UPSTREAM_HTTP_ERROR")
        return NormalizedError(
            error_id=error_id,
            code=defn.code,
            category=ErrorCategory.NETWORK.value,
            severity=ErrorSeverity.ERROR.value,
            message=f"Upstream server responded with HTTP {exc.code}: {exc.reason}",
            operation=operation,
            component=component or "RemoteFetch",
            stage=stage or "network",
            retryable=is_transient,
            user_actionable=exc.code in (400, 401, 403, 404),
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            evidence={"status_code": exc.code, "reason": str(exc.reason)},
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    if isinstance(exc, urllib.error.URLError):
        defn = get_error_definition("UNREACHABLE_SOURCE")
        return NormalizedError(
            error_id=error_id,
            code=defn.code,
            category=ErrorCategory.NETWORK.value,
            severity=ErrorSeverity.ERROR.value,
            message=f"Network error communicating with upstream source: {exc.reason}",
            operation=operation,
            component=component or "RemoteFetch",
            stage=stage or "network",
            retryable=True,
            user_actionable=True,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            evidence={"reason": str(exc.reason)},
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    if isinstance(exc, TimeoutError):
        defn = get_error_definition("UPSTREAM_TIMEOUT")
        return NormalizedError(
            error_id=error_id,
            code=defn.code,
            category=ErrorCategory.TIMEOUT.value,
            severity=ErrorSeverity.ERROR.value,
            message="Operation timed out waiting for upstream dependency or computation",
            operation=operation,
            component=component,
            stage=stage or "timeout",
            retryable=True,
            user_actionable=False,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    # 5. File and system errors
    if isinstance(exc, FileNotFoundError):
        code = "ARTIFACT_NOT_FOUND" if (artifact_uri or (component and "artifact" in component.lower())) else "FILE_NOT_FOUND"
        defn = get_error_definition(code)
        return NormalizedError(
            error_id=error_id,
            code=code,
            category=defn.category.value,
            severity=defn.severity.value,
            message=f"Requested resource or file was not found: {exc}",
            operation=operation,
            component=component,
            stage=stage,
            retryable=False,
            user_actionable=True,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            evidence={"filename": getattr(exc, "filename", None)},
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    if isinstance(exc, PermissionError):
        defn = get_error_definition("AUTH_FORBIDDEN")
        return NormalizedError(
            error_id=error_id,
            code=defn.code,
            category=ErrorCategory.AUTHORIZATION.value,
            severity=ErrorSeverity.ERROR.value,
            message="Filesystem or resource permission denied",
            operation=operation,
            component=component,
            stage=stage,
            retryable=False,
            user_actionable=False,
            suggested_action=defn.suggested_action,
            original_error=original_error,
            cause_chain=cause_chain,
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    # 6. SciPy / PyMC-Marketing Optimization errors
    exc_type_name = type(exc).__name__
    if "MinimizeException" in exc_type_name or "OptimizationError" in exc_type_name:
        defn = get_error_definition("OPTIMIZATION_FAILED")
        return NormalizedError(
            error_id=error_id,
            code=defn.code,
            category=ErrorCategory.OPTIMIZATION.value,
            severity=ErrorSeverity.ERROR.value,
            message=f"Optimization solver failed: {exc}",
            operation=operation or "optimize_budget",
            component=component or "DecisionService",
            stage=stage or "solver",
            retryable=True,
            user_actionable=True,
            suggested_action="Review budget bounds, relaxation constraints, and optimizer convergence",
            original_error=original_error,
            cause_chain=cause_chain,
            evidence={"solver_status": "exception", "optimizer_message": str(exc)},
            context=ctx,
            request_id=request_id,
            job_id=job_id,
            dataset_id=dataset_id,
            model_id=model_id,
            tenant_id=tenant_id,
            artifact_uri=artifact_uri,
            stack_trace=tb_str,
        )

    # 7. Fallback: Unknown / unhandled internal exception
    defn = get_error_definition("INTERNAL_ERROR")
    return NormalizedError(
        error_id=error_id,
        code=defn.code,
        category=ErrorCategory.INTERNAL.value,
        severity=ErrorSeverity.ERROR.value,
        message="The operation failed unexpectedly. An internal diagnostic event was recorded.",
        user_message="An unexpected system failure occurred",
        operation=operation,
        component=component,
        stage=stage,
        retryable=False,
        user_actionable=False,
        suggested_action=f"Report error_id {error_id} to the service operator",
        original_error=original_error,
        cause_chain=cause_chain,
        context=ctx,
        request_id=request_id,
        job_id=job_id,
        dataset_id=dataset_id,
        model_id=model_id,
        tenant_id=tenant_id,
        artifact_uri=artifact_uri,
        stack_trace=tb_str,
    )


def classify_domain_error(err: DomainError) -> NormalizedError:
    """Normalize a DomainError instance directly."""
    return classify_exception(err)
