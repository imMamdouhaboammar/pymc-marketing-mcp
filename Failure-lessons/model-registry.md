# Failure Lessons: Model Registry & Identity Resolution

This document captures durable failure lessons, root causes, and architectural invariants for model registry consistency, typed identifier resolution, and cross-endpoint model lookup in `pymc-marketing-mcp`.

---

## CLV-REG-001: Typed Model Identity Resolution Asymmetry

### What happened
After successfully fitting a CLV model using `fit_clv_model`, the tool response returned `model_id: "clv_bg_nbd_98234"`. However, when the caller subsequently passed this exact identifier to `get_clv_model(model_id="clv_bg_nbd_98234")` or `predict_clv(model_id="clv_bg_nbd_98234")`, the lookup failed with:
```text
ModelNotFoundError: Model 'clv_bg_nbd_98234' not found in registry
```
Conversely, if the caller passed the bare UUID `"98234"`, some endpoints succeeded while others failed.

### Why it mattered
* **Workflow Disruption**: In autonomous multi-tool agent workflows (e.g. `fit_clv_model` $\to$ `predict_clv` $\to$ `calculate_clv`), the inability to resolve an ID emitted by the immediately preceding tool breaks the automation loop.
* **Confusing Developer Experience**: Callers could see the model in database tables or logs, but programmatic API lookups insisted it did not exist.

### Observable symptom
* Intermittent `ModelNotFoundError` on newly created models.
* ID lookup sensitivity: endpoints requiring `clv:id`, `clv_bg_nbd:id`, or raw `id` without uniform normalization.

### Initial assumption
Developers assumed that separate service modules (`MMMService` and `CLVService`) could each manage their own ID conventions and prefixing rules independently.

### Root cause
* **Status**: Confirmed.
* **Decoupled Key Formatting**:
  - The model fitting tool saved records into metadata storage using a prefixed key (e.g., `f"clv_bg_nbd_{model_uuid}"`).
  - The model lookup service queried the database using the raw UUID, stripping the prefix before querying or querying with raw strings inconsistently.
  - Downstream prediction tools queried by raw UUID and expected the registry to find it by primary key.
* No centralized normalization existed to map aliases, prefixes, and UUIDs to canonical storage keys.

### Why the system allowed it
The repository had multiple ad-hoc dictionary lookup and SQL query patterns scattered across different service classes instead of routing through a single canonical registry resolver.

### Fix
1. **Canonical Resolver Gateway**: Implemented `ModelRegistry.resolve(model_id, expected_type=None)` in `src/marketing_mcp/storage/metadata.py` and `services/`:
   - Normalizes input IDs: handles bare UUIDs (`"98234"`), prefixed strings (`"clv:98234"`, `"clv_bg_nbd_98234"`), and URI schemes (`"model://mmm/98234"`).
   - Resolves canonical database records regardless of the format supplied by the caller.
2. **Strict Type Discrimination**: If `expected_type` is specified (e.g. `CLV` vs `MMM`), the resolver verifies model family invariants:
   - If the model exists but belongs to a different family, it raises `ModelTypeMismatchError` (400) rather than `ModelNotFoundError` (404), providing clear diagnostic feedback.
3. **Canonical Output Formatting**: All API responses now emit canonical, prefixed identifiers that round-trip cleanly into all consumer endpoints.

### Verification
* `tests/unit/test_hard_test_remediation.py::test_unified_model_registry_resolution_across_types`
* Verifies that bare UUIDs, prefixed keys, and typed queries resolve to the exact same underlying model record across both MMM and CLV workflows.

### Prevention rule
> **Rule**: Model identity and resolution must have one canonical implementation. All endpoints must resolve model records through a centralized resolver that normalizes prefixes and verifies type invariants.

### Reusable lesson
Whenever entity identifiers are namespaced or prefixed by type, enforce bidirectional normalization in a single resolver module. Never allow individual endpoint handlers to concatenate or slice ID strings.

### Related failures
* `model-lineage.md`: CLV Multi-Model Lineage Bypass
* `artifact-lifecycle.md`: Atomic Publication & Readiness

---

## Protected Systems & Code References

* `src/marketing_mcp/storage/metadata.py`: [`MetadataStorage.resolve_model`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/storage/metadata.py)
* `src/marketing_mcp/services/clv_service.py`: Unified CLV model lookup and validation
* `src/marketing_mcp/errors.py`: [`ModelTypeMismatchError`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/errors.py)
* `tests/unit/test_hard_test_remediation.py`: Registry resolution parity tests
