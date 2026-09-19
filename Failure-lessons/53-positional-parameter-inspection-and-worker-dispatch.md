# Lesson 53: Positional Parameter Inspection and Exactly-Once Worker Dispatch

### Context
Subprocess worker dispatch (`src/marketing_mcp/jobs/process_worker.py`) where background jobs execute arbitrary Python callables with optional cooperative cancellation events (`cancel_event`).

### What happened
When inspecting handler signatures via `inspect.signature(handler)`, the code checked `"cancel_event" in sig.parameters` and dispatched `handler(job, cancel_event=cancel_event)`. For handlers defined with positional-only syntax (e.g. `def handler(job, cancel_event, /)`), Python raised `TypeError: handler() got some positional-only arguments passed as keyword arguments: 'cancel_event'`.

Previously, the worker attempted to catch `TypeError` as a runtime fallback:
```python
try:
    result = handler(job, cancel_event)
except TypeError:
    result = handler(job)
```
When an internal bug inside the handler raised a `TypeError` (e.g. type mismatch in mathematical expressions), the worker misidentified this as an arity error and called `handler(job)` again, causing duplicate execution of expensive and failing compute.

### Observable symptom
```text
TypeError: handler() got some positional-only arguments passed as keyword arguments: 'cancel_event'
```
Or, with the naive catch-all `TypeError` fallback:
Duplicate execution logs and repeated heavy MCMC sampling allocations when an internal `TypeError` occurred inside the handler.

### Impact
- **Reliability & Resource Protection**: Compute tasks either crashed on invocation or executed twice upon encountering internal type errors, consuming excess GPU/CPU resources and causing duplicate side-effects.
- **Compute Integrity**: Exactly-once execution guarantees were broken.

### Incorrect assumption
Assumed that if a parameter named `cancel_event` exists in `sig.parameters`, it can always be passed as a keyword argument (`cancel_event=cancel_event`). Also assumed catching `TypeError` around invocation is an acceptable way to test callable arity at runtime.

### Root cause
**Confirmed**.
1. `inspect.Parameter` distinguishes between `POSITIONAL_ONLY`, `POSITIONAL_OR_KEYWORD`, `VAR_POSITIONAL`, and `KEYWORD_ONLY`. Checking `"cancel_event" in sig.parameters` does not guarantee keyword compatibility.
2. Catching `TypeError` around a function invocation conflates *call-site parameter binding errors* with *internal runtime errors* raised from inside the function body.

### Why the architecture allowed it
The worker relied on dynamic duck-typing invocation with exception fallback rather than upfront reflection of parameter kinds.

### Fix
1. Removed all `try...except TypeError` invocation fallbacks. Arity and binding style are determined strictly before invocation.
2. Inspected `cancel_param.kind`:
```python
# In src/marketing_mcp/jobs/process_worker.py
sig = inspect.signature(handler)
params = list(sig.parameters.values())
cancel_param = sig.parameters.get("cancel_event")
has_cancel_kw = cancel_param is not None and cancel_param.kind in (
    inspect.Parameter.POSITIONAL_OR_KEYWORD,
    inspect.Parameter.KEYWORD_ONLY,
)
has_two_pos = len([
    p for p in params
    if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
]) >= 2
has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)

if has_cancel_kw:
    result = handler(job, cancel_event=cancel_event)
elif has_two_pos or has_varargs:
    result = handler(job, cancel_event)
else:
    result = handler(job)
```

### Verification
- `tests/unit/test_process_worker.py::test_worker_dispatches_positional_only_cancel_event`
- `tests/unit/test_process_worker.py::test_worker_does_not_retry_on_internal_type_error`
- `tests/unit/test_process_worker.py::test_worker_dispatches_keyword_cancel_event`
- `tests/unit/test_process_worker.py::test_worker_dispatches_single_arg_handler`

### Prevention rule
> **Never catch `TypeError` at the call site to detect function arity; always inspect `inspect.signature` parameter kinds (`POSITIONAL_ONLY`, `KEYWORD_ONLY`, `VAR_POSITIONAL`) before invocation to guarantee exactly-once execution.**

### Reusable lesson
In dynamic dispatchers, plugins, and worker runtimes, Python 3.8+ positional-only parameters (`/`) break naive keyword passing. Arity detection must happen reflectively before the call, never via runtime exception catching.

### Related code
- `src/marketing_mcp/jobs/process_worker.py`

### Related tests
- `tests/unit/test_process_worker.py`

### Status
Solved (commits `1402af8` and `81de4c0`, merged in `69f6280`)
