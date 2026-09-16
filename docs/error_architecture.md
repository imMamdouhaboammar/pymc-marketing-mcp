# Production-Grade Error Normalization and Diagnostic Error Architecture

## 1. Executive Summary & Core Invariants

The `pymc-marketing-mcp` service enforces a centralized, production-grade error normalization and diagnostic architecture. In high-reliability and multi-agent marketing environments, silent failures, generic stack traces, leaked credentials, or inconsistent error envelopes degrade agent autonomy and impede operational observability.

This architecture ensures that **every failure across the entire MCP surface** is:
- **Traceable**: Tagged with a collision-resistant, unique `error_id` (`err_<timestamp>_<hex>`).
- **Classifiable**: Categorized into a strict taxonomy of 10 canonical categories and 87 error definitions.
- **Actionable**: Provides immediate operational answers regarding retryability, user-remediability, code fixes, and machine-readable `next_action` suggestions.
- **Root-Cause Preserving**: Retains the original exception class, message, and cause chain (`__cause__` / `__context__`).
- **Zero-Leakage Secure**: Scrubs all Bearer tokens, JWTs, API keys, signed URL query signatures, and database credentials before emission, while strictly containing raw tracebacks to server-side diagnostic systems.
- **100% Backward Compatible**: Guarantees existing domain error codes (`OPTIMIZATION_FAILED`, `MODEL_NOT_FOUND`, `DATASET_NOT_FOUND`, etc.) and MCP client contracts (`err["code"]`, `err["message"]`, `err["evidence"]`, `err["next_action"]`) remain untouched.

---

## 2. Canonical Error Taxonomy & Catalog

Errors are classified along two dimensions: **Category** (`ErrorCategory`) and **Severity** (`ErrorSeverity`).

### 2.1 Categories (`ErrorCategory`)
1. `VALIDATION_ERROR`: Schema mismatches, parameter type violations, missing required arguments.
2. `DATASET_ERROR`: Dataset not found, empty payload, invalid format, column type mismatch, SSRF / forbidden path.
3. `MODEL_ERROR`: Model spec missing, incompatible architecture, uncalibrated parameters, state corruption.
4. `STATISTICAL_ERROR`: MCMC convergence failure, R-hat threshold breach, high divergences, BFMI failure, line-search budget failure.
5. `OPTIMIZATION_ERROR`: Budget allocation bounds violation, non-convex optimizer divergence, infeasible constraints.
6. `SYSTEM_ERROR`: Out of memory (OOM), storage full, hardware or runtime failures.
7. `STORAGE_ERROR`: Database locked, disk I/O error, artifact serialization/deserialization failure.
8. `AUTHENTICATION_ERROR`: Missing or invalid tenant token, signature mismatch, expired session.
9. `AUTHORIZATION_ERROR`: Cross-tenant access violation, unauthorized project or resource access.
10. `UPSTREAM_ERROR`: Remote HTTP errors, connection timeouts, DNS lookup failures from external sources.

### 2.2 Severities (`ErrorSeverity`)
- `DEBUG`: Informational diagnostics during dry runs or non-critical soft checks.
- `INFO`: User-recoverable notifications (e.g. invalid date format).
- `WARNING`: Recoverable issue or transient condition (e.g. retryable DB lock, upstream timeout).
- `ERROR`: Standard domain operation failure requiring user correction or parameter adjustment.
- `CRITICAL`: Unhandled exceptions, system invariants violated, or failures requiring engineering intervention.

---

## 3. The Unified Error Envelope

Every tool failure returned to an MCP client conforms to the canonical envelope. It preserves legacy fields while enriching the response with actionable diagnostic metadata.

### 3.1 Public MCP Response Schema

```json
{
  "error": {
    "code": "DATASET_NOT_FOUND",
    "message": "Dataset 'q4_spend' was not found in project 'retail_mmm'.",
    "error_id": "err_20260916_142031_a1b2c3d4",
    "category": "dataset_error",
    "severity": "error",
    "retryable": false,
    "user_fixable": true,
    "requires_code_fix": false,
    "suggested_fix": "Verify that the dataset was uploaded and register it with upload_dataset.",
    "next_action": "upload_dataset",
    "evidence": {
      "dataset_name": "q4_spend",
      "project_id": "retail_mmm"
    },
    "original_error": {
      "type": "KeyError",
      "message": "q4_spend",
      "cause_chain": ["KeyError: q4_spend"]
    }
  }
}
```

### 3.2 11 Core Reliability Questions Answered

| Question | Corresponding Field | Purpose |
| :--- | :--- | :--- |
| **What failed?** | `error.message` & `error.code` | Clear, human- and LLM-readable failure summary |
| **Where it failed?** | `error.evidence.operation` / module | Source tool and execution locus |
| **Which operation was running?** | `operation` metadata / evidence | Context passed to the error boundary |
| **Which domain owns the failure?** | `error.category` | Ownership boundary (validation, dataset, statistical, etc.) |
| **What the original exception was?** | `error.original_error` | Raw exception type, message, and cause chain |
| **What normalized MCP category applies?** | `error.category` | Canonical routing taxonomy |
| **Whether retrying can help?** | `error.retryable` | Machine-readable retry signal (e.g., `True` for DB locks) |
| **Whether user input can fix it?** | `error.user_fixable` | Clarifies whether caller changed inputs can succeed |
| **Whether engineering fix is needed?** | `error.requires_code_fix` | Flag for on-call SRE and bug tracking alerts |
| **What actions / tools to run next?** | `error.next_action` & `suggested_fix`| Concrete tool invocation suggestion (e.g., `upload_dataset`) |
| **Which correlation ID to reference?** | `error.error_id` | Unique ID for log searching and diagnostic registry lookup |

---

## 4. Secret Redaction & Traceback Containment

Security and privacy invariants are strictly enforced: **credentials and raw tracebacks never leave the server process.**

### 4.1 Scrubbing Pipeline
All strings, dictionaries, evidence objects, and URLs pass through `redact_secrets()` and `redact_url()` in `src/marketing_mcp/security/redaction.py`:
- **Bearer Tokens**: `Bearer eyJ...` $\rightarrow$ `Bearer [REDACTED]`
- **JWTs**: Standard 3-segment base64 JWT patterns $\rightarrow$ `[REDACTED_JWT]`
- **Key-Value Credentials**: Matches `api_key=...`, `secret=...`, `password=...`, `token=...` $\rightarrow$ `key=[REDACTED]`
- **Database Connection URIs**: `postgresql://user:pass@host:5432/db` $\rightarrow$ `postgresql://user:[REDACTED]@host:5432/db`
- **Cloud Signed URL Signatures**: Query parameters including `X-Amz-Signature`, `X-Goog-Signature`, `signature=`, and `sig=` are masked to `[REDACTED]`.

### 4.2 Traceback Containment
Full Python tracebacks are:
1. **Never included in the public response dictionary** (`to_mcp_response()` or `to_public_dict()`).
2. **Logged server-side** using structured logging (`structlog` / logger with `exc_info=True`).
3. **Stored in the bounded diagnostic registry** (`GLOBAL_ERROR_REGISTRY`) accessible exclusively to system administrators and operators.

---

## 5. Classification Engine (`error_classifier.py`)

The classifier inspects incoming exceptions and builds a complete `NormalizedError`:

```text
Incoming Exception
       │
       ├── DomainError ───────────────────► Preserve domain code, evidence & next_action; enrich metadata
       ├── pydantic.ValidationError ──────► Map to VALIDATION_ERROR, extract offending field paths
       ├── sqlite3.OperationalError ──────► Detect "database is locked" -> DATABASE_LOCKED (retryable=True)
       │                                     other -> STORAGE_ERROR
       ├── sqlite3.IntegrityError ────────► Map to STORAGE_ERROR / INTEGRITY_VIOLATION
       ├── urllib.error.HTTPError ────────► Map to UPSTREAM_HTTP_ERROR (preserve HTTP status in evidence)
       ├── TimeoutError / URLError ───────► Map to UPSTREAM_TIMEOUT (retryable=True)
       ├── FileNotFoundError ─────────────► Map to FILE_NOT_FOUND (user_fixable=True)
       ├── PermissionError ───────────────► Map to STORAGE_ERROR / PERMISSION_DENIED
       └── Unhandled / Unknown Exception ─► Map to INTERNAL_ERROR (severity=CRITICAL, requires_code_fix=True)
```

### Cause Chain Extraction
`extract_cause_chain(exc)` traverses `__cause__` and `__context__` recursively up to 10 levels deep, generating a clear chain of causal exceptions without leaking stack trace lines.

---

## 6. Universal Error Boundary (`@mcp_error_boundary`)

Every MCP tool function is decorated with `@mcp_error_boundary`:

```python
from marketing_mcp.error_boundary import mcp_error_boundary

@mcp_error_boundary(operation="sample_mmm", domain="mmm")
async def sample_mmm_tool(dataset_name: str, target_column: str, ...) -> dict[str, Any]:
    ...
```

### Execution Lifecycle:
1. **Invocation**: Executes the underlying coroutine or function.
2. **Exception Interception**: Catches all `Exception` instances.
3. **Classification**: Calls `classify_exception(exc, operation=operation, default_domain=domain, extra_context=...)`.
4. **Registry Storage**: Records the full diagnostic profile in `GLOBAL_ERROR_REGISTRY`.
5. **Observability Dispatch**:
   - Increments Prometheus metrics: `GLOBAL_METRICS.record_error(category=..., code=..., domain=...)`.
   - Emits structured JSON log event: `logger.error("operation_failed", error_id=..., ...)` with `exc_info`.
6. **Client Response**: Returns `{"error": normalized_error.to_public_dict()}` to the MCP transport.

---

## 7. Operator Diagnostics & CLI Tooling

When a client reports an `error_id`, operators can immediately inspect the un-redacted root cause and stack trace without searching raw log files.

### 7.1 Diagnostic Registry (`ErrorDiagnosticRegistry`)
- Thread-safe, in-memory bounded LRU cache (default: 1,000 entries).
- Records full Python traceback, operation context, tenant ID, and cause chain.

### 7.2 CLI Lookup Tool
Operators inspect error details via the CLI:

```bash
# Using subcommand
marketing-mcp lookup-error err_20260916_142031_a1b2c3d4

# Using flag
marketing-mcp --lookup-error err_20260916_142031_a1b2c3d4
```

**Sample Output:**
```json
{
  "error_id": "err_20260916_142031_a1b2c3d4",
  "code": "DATASET_NOT_FOUND",
  "category": "dataset_error",
  "severity": "error",
  "message": "Dataset 'q4_spend' was not found in project 'retail_mmm'.",
  "operation": "load_dataset",
  "domain": "dataset",
  "timestamp": "2026-09-16T14:20:31.123456+00:00",
  "retryable": false,
  "user_fixable": true,
  "requires_code_fix": false,
  "suggested_fix": "Verify that the dataset was uploaded and register it with upload_dataset.",
  "next_action": "upload_dataset",
  "evidence": {
    "dataset_name": "q4_spend"
  },
  "original_error": {
    "type": "KeyError",
    "message": "'q4_spend'",
    "cause_chain": ["KeyError: 'q4_spend'"]
  },
  "traceback": [
    "Traceback (most recent call last):\n",
    "  File \".../dataset_service.py\", line 45, in load\n    return self._datasets[name]\nKeyError: 'q4_spend'\n"
  ]
}
```

---

## 8. Verification & Test Coverage

The error architecture is validated against rigorous unit, security, and integration suites:
- `tests/unit/test_error_normalization.py`: Validates catalog completeness, format compliance, cause chain extraction, classification accuracy, and boundary encapsulation.
- `tests/security/test_error_secret_leakage.py`: Confirms zero secret leakage (Bearer tokens, DB credentials, signed URL query signatures) and verified traceback containment.
