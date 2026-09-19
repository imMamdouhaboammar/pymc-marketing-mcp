# Lesson 46: Bogus Provenance Acceptance on Uncalibrated Confidence Scores

### Context
Portfolio entity graph edge contracts (`src/marketing_mcp/domain/portfolio/contracts.py`) defining directional marketing spillovers, halos, and cannibalization coefficients.

### What happened
During the removal of arbitrary heuristic defaults (`confidence = 0.8`), `PortfolioEffectEdge` was updated so that `confidence` defaults to `None` (uncalibrated) with `confidence_provenance="unspecified"`. However, the Pydantic `@model_validator` was written asymmetrically:
```python
if self.confidence is not None and self.confidence_provenance == "unspecified":
    self.confidence_provenance = "caller_specified"
return self
```
It failed to validate the converse case: when `confidence` was `None`, a caller could explicitly supply `confidence_provenance="empirical_precision"` or `"caller_specified"` without any numeric confidence score.

### Observable symptom
Cubic AI reviewer flagged a P2 violation on commit `0a4e3f2`:
```text
P2: When `confidence` is `None`, this validator still accepts `empirical_precision` or `caller_specified` provenance, even though `None` means uncalibrated. Reject non-`unspecified` provenance without a confidence score so downstream audits cannot treat an uncalibrated edge as calibrated.
```

### Impact
Downstream audit ledgers and decision governance filters that query edges by `confidence_provenance in ("empirical_precision", "caller_specified")` would treat uncalibrated edges (`confidence=None`) as calibrated empirical inputs, defeating epistemic audit safety.

### Incorrect assumption
Assumed that checking `if self.confidence is not None` to upgrade provenance from `"unspecified"` to `"caller_specified"` was sufficient, implicitly assuming callers would never pass a calibrated provenance string alongside a `None` score.

### Root cause
**Confirmed**. The validator lacked a fail-closed guard enforcing correlation between the presence of a numeric confidence value and its provenance claim.

### Why the architecture allowed it
Pydantic fields validate their own types individually; cross-field invariants require explicit model validators. When writing the model validator, only the auto-upgrade branch was written, omitting the negative constraint.

### Fix
Added strict fail-closed validation in `_validate_edge_semantics`:
```python
if self.confidence is None and self.confidence_provenance != "unspecified":
    raise ValueError(
        f"confidence_provenance must be 'unspecified' when confidence is None, "
        f"got '{self.confidence_provenance}'"
    )
if self.confidence is not None and self.confidence_provenance == "unspecified":
    self.confidence_provenance = "caller_specified"
```
Added regression unit test `test_edge_validation_rejects_provenance_without_confidence` in `tests/unit/test_portfolio_graph.py`.

### Verification
1. `uv run pytest tests/unit/test_portfolio_graph.py -v` passes (9/9 passed).
2. Attempting to instantiate `PortfolioEffectEdge(..., confidence=None, confidence_provenance="empirical_precision")` raises `ValidationError`.
3. Pushed commit `f3dc8a5`, clearing Cubic AI code review cleanly.

### Prevention rule
> **Audit provenance attributes must fail-closed: if the quantified score, value, or certificate is null, any provenance tag claiming empirical calibration or explicit specification must be strictly rejected.**

### Related code
- `src/marketing_mcp/domain/portfolio/contracts.py`

### Related tests
- `tests/unit/test_portfolio_graph.py::TestPortfolioGraph::test_edge_validation_rejects_provenance_without_confidence`

### Related lessons
- [24-prior-sensitivity-contract-fidelity.md](./24-prior-sensitivity-contract-fidelity.md)
- [38-dual-parse-protocol-boundary-and-typed-contracts.md](./38-dual-parse-protocol-boundary-and-typed-contracts.md)

### Status
Resolved
