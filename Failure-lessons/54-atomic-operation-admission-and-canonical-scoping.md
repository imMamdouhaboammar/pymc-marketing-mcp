# Lesson 54: Atomic Direct-Operation Admission and Scoped Canonical Identities

### Context
Direct-operation concurrency and cancellation guard (`src/marketing_mcp/jobs/operation_guard.py`) managing in-flight synchronous and heavy threadpool operations (`fit_mmm`, `optimize_budget`, `transform_ad_export`).

### What happened
`run_tracked_executor()` originally checked `_active` operations under `_lock`, released the lock, and then called `register_operation()`, which acquired the lock a second time. In concurrent execution scenarios, two identical requests arrived simultaneously, both passed the initial check before either registered, and both started duplicate heavy CPU operations.

Additionally, operation identity was originally un-scoped or keyed on raw string labels, creating multi-tenant collisions where one tenant's operation could conflict with another's.

### Observable symptom
Under concurrent load or adversarial test barriers:
```text
AssertionError: Expected DomainError('OPERATION_ALREADY_RUNNING'), but both concurrent requests were admitted
```
Two identical operations executed concurrently in separate threads, duplicating CPU/GPU compute and causing race conditions on shared disk artifacts.

### Impact
- **Performance & Cloud Cost**: Redundant MCMC sampling and optimization runs wasted compute capacity.
- **Multi-Tenant Safety**: Un-scoped keys could cause cross-tenant throttling or false collision rejections when different tenants submitted jobs with default parameters.

### Incorrect assumption
Assumed that separating "check if running" from "register operation" into two sequential lock acquisitions was safe because both touched the same underlying dictionary.

### Root cause
**Confirmed**.
Classic Time-of-Check to Time-of-Use (TOCTOU) race condition between scanning `_active` and inserting into `_active`.

### Why the architecture allowed it
The check was placed in the outer caller (`run_tracked_executor`) while registration was placed in a helper method (`register_operation`), splitting what should have been an atomic critical section.

### Fix
1. Consolidated check-and-insert into a single atomic critical section inside `register_operation()`:
```python
# In src/marketing_mcp/jobs/operation_guard.py
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
    op = ActiveOperation(...)
    self._active[op_id] = op
    return op
```

2. Implemented `canonical_operation_identity()` producing deterministic SHA-256 digests partitioned by `op_type`, `tenant_id`, `owner`, and recursively sorted/normalized semantic payloads:
```python
def canonical_operation_identity(
    op_type: str,
    principal: Any = None,
    payload: Any = None,
) -> str:
    tenant_id = getattr(principal, "tenant_id", None) if principal else None
    owner = getattr(principal, "subject", "local") if principal else "local"
    # Normalizes Pydantic models, dicts (sorted keys), lists, sets
    envelope = {
        "op_type": op_type,
        "tenant_id": str(tenant_id or "default"),
        "owner": str(owner or "anonymous"),
        "payload": _normalize(payload),
    }
    canonical_bytes = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical_bytes).hexdigest()[:16]
    return f"op_ident_{op_type}_{digest}"
```

### Verification
- `tests/unit/test_heavy_tools_cancellation.py::test_concurrent_duplicate_operation_admission_is_atomic` (barrier synchronization testing 2 simultaneous threads arriving at the exact same instant)
- `tests/unit/test_heavy_tools_cancellation.py::test_canonical_operation_identity_isolation`

### Prevention rule
> **In-flight resource admission must be atomic within a single lock acquisition; never release a lock between checking for existing execution and registering new execution.**

### Reusable lesson
Operation deduplication and concurrency control must follow atomic test-and-set semantics. Multi-tenant operations must include tenant and principal identity in their deduplication keys to prevent cross-tenant collision.

### Related code
- `src/marketing_mcp/jobs/operation_guard.py`
- `src/marketing_mcp/mcp/tools/datasets.py`
- `src/marketing_mcp/mcp/tools/decisions.py`
- `src/marketing_mcp/mcp/tools/mmm.py`

### Related tests
- `tests/unit/test_heavy_tools_cancellation.py`

### Status
Solved (commit `1402af8`, merged in `69f6280`)
