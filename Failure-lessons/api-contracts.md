# Failure Lessons: API Contracts, Error Taxonomy & Actionable Guidance

This document captures durable failure lessons, root causes, and architectural invariants for machine-readable error contracts, user-error classification, and tool-registry-grounded `next_actions` in `pymc-marketing-mcp`.

---

## API-ERR-001: Caller Input Errors Swallowed as Internal Server Errors

### What happened
When a caller or AI agent submitted a malformed date format, an unknown marketing channel name, or a duplicate customer identifier:
* The tool handler crashed internally and was intercepted by a global fallback `except Exception:` block.
* The API returned:
  ```json
  {
    "status": "error",
    "error_code": "INTERNAL",
    "message": "Internal server error occurred: 'date'"
  }
  ```
  accompanied by a raw Python traceback.

### Why it mattered
* **Autonomous Agent Loop Paralysis**: Autonomous AI agents interpret `INTERNAL` as an ephemeral infrastructure outage or server defect. Agents either repeatedly retry the exact same malformed payload (burning token quotas) or abandon the task entirely, failing to correct their own input errors.
* **Security Exposure**: Unformatted stack traces leak internal filesystem paths, package versions, and implementation details.

### Observable symptom
* Client logs littered with `INTERNAL` (500) status codes on client-side input errors.
* Agents unable to self-heal or correct input parameters.

### Initial assumption
Developers assumed that wrapping entire tool handlers in a generic `try...except Exception` that maps everything to `INTERNAL` provided a robust safety net against unhandled crashes.

### Root cause
* **Status**: Confirmed.
* **Absence of an Error Classification Boundary**: The platform lacked a normalized error hierarchy mapping specific domain exceptions (`DatasetValidationError`, `ModelNotFoundError`, `InvalidStateTransitionError`, `ModelLineageError`) to canonical HTTP/MCP status codes.
* Domain modules raised standard Python exceptions (`KeyError`, `ValueError`) which the top-level envelope could not distinguish from unexpected system crashes.

### Why the system allowed it
Error handling was treated as an afterthought at the endpoint perimeter rather than a typed architectural contract.

### Fix
1. **Centralized Error Normalization Layer**: Created `src/marketing_mcp/error_classifier.py` and structured domain exceptions in `src/marketing_mcp/errors.py`:
   - `DatasetValidationError` $\longrightarrow$ `INVALID_INPUT` (400)
   - `ModelNotFoundError` $\longrightarrow$ `NOT_FOUND` (404)
   - `ModelLineageError` $\longrightarrow$ `PRECONDITION_FAILED` (412)
   - `InvalidStateTransitionError` $\longrightarrow$ `CONFLICT` (409)
   - `ResourceLimitExceededError` $\longrightarrow$ `UNPROCESSABLE_ENTITY` (422)
2. **Machine-Actionable Error Envelopes**: Error responses now include structured diagnostics:
   ```json
   {
     "status": "error",
     "error_code": "INVALID_INPUT",
     "error_type": "DatasetValidationError",
     "message": "Column 'spend' contains negative values",
     "retryable": false,
     "remediation_hint": "Ensure all marketing spend values are >= 0.0 before submission."
   }
   ```
3. **Traceback Sanitization**: Raw tracebacks are logged internally but suppressed from public MCP envelopes.

### Verification
* `tests/unit/test_error_normalization.py`
* `tests/unit/test_hard_test_remediation.py::test_error_classification_taxonomy`
* Asserts that bad inputs return `INVALID_INPUT` with remediation hints, not `INTERNAL`.

### Prevention rule
> **Rule**: Caller errors are never INTERNAL errors. All domain and validation exceptions must map to a standardized, machine-readable error taxonomy with explicit remediation guidance.

### Reusable lesson
For AI agent interfaces, errors are instructions. Every error message must clearly state what was wrong, whether it is retryable, and what specific action will resolve it.

---

## API-NEXT-001: Hallucinated & Uncallable `next_actions` Recommendations

### What happened
Several tool responses included a `next_actions` array suggesting workflow continuations, such as:
```json
{
  "next_actions": [
    "run_cross_validation",
    "export_to_tableau",
    "inspect_adstock_weights"
  ]
}
```
When autonomous AI agents attempted to execute these suggested tools, the server rejected the calls with:
```text
ToolNotFoundError: Tool 'run_cross_validation' not found in registry
```

### Why it mattered
* **Autonomous Execution Failure**: AI agents rely heavily on suggested next steps to navigate complex multi-tool workflows. Suggesting non-existent tools causes agents to hallucinate arguments, attempt invalid executions, and fail their missions.
* **Developer Confusion**: Human developers spent hours searching documentation for tools that existed only as aspirational roadmap items.

### Observable symptom
* Autonomous agents crashing on step 2 of multi-step workflows.
* Tool catalog discovery mismatches between envelope suggestions and MCP manifests.

### Initial assumption
Developers wrote `next_actions` as free-form human advice, assuming agents would treat them as informal suggestions.

### Root cause
* **Status**: Confirmed.
* `next_actions` were hardcoded strings in tool return dictionaries with zero programmatic linkage to the active MCP tool registry.

### Why the system allowed it
The response envelope constructor had no dependency on or validation against `ToolRegistry`.

### Fix
1. **ActionRuntimePolicy Enforcement**: Created `ActionRuntimePolicy` in `src/marketing_mcp/mcp/envelope.py`:
   - Inspects every proposed string in `next_actions`.
   - Validates candidate actions against `ToolRegistry.list_tool_names()`.
   - If a suggested action does not exist in the active runtime tool catalog, it is automatically filtered out or rejected.
2. **Typed Next Action Builders**: Replaced raw string lists with typed action builders that reference registered tool symbols directly.

### Verification
* `tests/unit/test_action_runtime_policy.py`
* `tests/unit/test_hard_test_remediation.py::test_next_actions_validated_against_registry`
* Asserts that hallucinated or uncallable tool names in `next_actions` are strictly rejected by the envelope policy.

### Prevention rule
> **Rule**: Machine-actionable next steps must originate from the actual capability registry, not free-form text. Every recommended action in an API envelope must correspond to a callable, registered tool in the current environment.

### Reusable lesson
Never expose suggested programmatic actions to AI agents without asserting against the live tool registry.

### Related failures
* [Failure Lesson 15: Universal MCP Agent Transport Interop](./15-universal-mcp-agent-transport-interop.md)
* `validation-contracts.md`: Validation Parity & Admission

---

## Protected Systems & Code References

* `src/marketing_mcp/error_classifier.py`: [`ErrorClassifier`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/error_classifier.py)
* `src/marketing_mcp/errors.py`: Domain exception taxonomy
* `src/marketing_mcp/mcp/envelope.py`: [`ActionRuntimePolicy`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/mcp/envelope.py) and envelope builders
* `tests/unit/test_error_normalization.py`: Error code mapping test suite
* `tests/unit/test_action_runtime_policy.py`: Next actions registry validation tests
