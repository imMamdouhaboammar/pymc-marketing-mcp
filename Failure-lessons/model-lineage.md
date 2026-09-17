# Failure Lessons: Model Lineage & Multi-Model Composition

This document captures durable failure lessons, root causes, and architectural invariants for model provenance, lineage verification, and statistical cohort integrity in `pymc-marketing-mcp`.

---

## CLV-001: Multi-Model Cross-Dataset Composition & Fail-Open Lineage Bypass

### What happened
The `calculate_clv` endpoint allowed composing a purchase frequency model (Beta-Geometric/NBD) trained on Dataset A with a monetary transaction model (Gamma-Gamma) trained on Dataset B simply because customer identifiers overlapped (`user_001` ... `user_100`), producing an invalid blended portfolio CLV estimate of ~$130,000.

### Why it mattered
* **Statistical Invalidation**: In Customer Lifetime Value modeling, BG/NBD models churn probability and transaction rate while Gamma-Gamma models monetary spend per transaction *for that specific cohort and temporal observation window*. Composing models from divergent datasets (e.g. different time periods, geographical regions, or currencies like USD vs EUR) creates an economic hallucination.
* **Silent Corruption**: The calculation completed without error, returning credible-looking lifetime value curves that misled marketing teams into overspending on churned customers.

### Observable symptom
* `calculate_clv(frequency_model_id="bg_nbd_cohort_2022", monetary_model_id="gg_cohort_2024")` returned a successful prediction envelope despite models originating from different data sources.
* Mixing a model trained in USD with a model trained in GBP produced unscaled numerical composites.

### Initial assumption
The original implementation assumed:
1. "If customer IDs overlap between dataset A and dataset B, they are the same customers and the models are compatible."
2. "Lineage check `if p_fp and v_fp and p_fp != v_fp: reject` is sufficient."

### Root cause
* **Status**: Confirmed.
* **Identity Overlap Fallacy**: Shared entity IDs do not constitute a shared statistical cohort. The same user `user_123` behaves differently across seasons, promotional periods, or customer lifecycles.
* **Fail-Open Verification**: The check `if p_fp and v_fp and p_fp != v_fp` only triggered if *both* fingerprints were non-empty strings. If either model had `dataset_fingerprint = None`, empty string `""`, or omitted metadata (common in mock fixtures or migrated models), the condition evaluated to `False` and passed silently.
* **Missing Invariant Coverage**: The system did not track or enforce currency matching, observation time horizons, or customer population hashing.

### Why the system allowed it
1. Lineage checking was treated as an optional defensive advisory rather than a mandatory, fail-closed gate.
2. Metadata schemas permitted models to be registered without strictly typed lineage attributes.

### Fix
1. **Fail-Closed Lineage Guard**: Replaced permissive conditions with strict fail-closed enforcement in `src/marketing_mcp/services/clv_service.py` and `ModelLineageGuard`:
   - Both models must present non-empty `dataset_id` and `dataset_fingerprint`.
   - If either fingerprint is missing or empty, immediately raise `ModelLineageError("UNVERIFIED_LINEAGE")`.
   - If `p_fp != v_fp`, raise `ModelLineageError("DATASET_MISMATCH")`.
2. **Currency Invariant Enforcement**: Both models must explicitly declare `currency` in their metadata; mismatches raise `ModelLineageError("CURRENCY_MISMATCH")`.
3. **Order-Invariant Population Fingerprint**: Validated customer population consistency via SHA-256 hash over canonical sorted customer IDs:
   $$\text{customer\_population\_fingerprint} = \text{SHA256}(\text{join}(\text{sorted}(\text{customer\_ids})))$$
4. **Lineage Audit Envelope**: Every multi-model composite response now includes the unified lineage manifest with verified dataset fingerprints.

### Verification
* `tests/unit/test_hard_test_remediation.py::test_clv_lineage_fails_closed_on_dataset_mismatch`
* `tests/unit/test_hard_test_remediation.py::test_clv_lineage_rejects_missing_fingerprint`
* `tests/unit/test_adversarial_torture_suite.py::test_clv_lineage_rejects_currency_and_population_divergence`

### Prevention rule
> **Rule**: Lineage checks must fail closed. Entity ID overlap $\ne$ modeling cohort. Both dataset fingerprint, currency, time bounds, and population hashes must match before multi-model composition is permitted.

### Reusable lesson
When composing outputs from multiple independently trained models:
1. Never validate compatibility using entity identity intersection alone.
2. Ensure cryptographic data fingerprints are mandatory schema fields.
3. Fail closed on missing, null, or unverified metadata.

### Related failures
* `validation-contracts.md`: Validation Parity & Dataset Fingerprinting
* `model-registry.md`: Model Identity & Typed Resolution

---

## Protected Systems & Code References

* `src/marketing_mcp/services/clv_service.py`: Lineage validation guard and composite CLV calculator
* `src/marketing_mcp/errors.py`: [`ModelLineageError`](file:///Users/mamdouhaboammar/Documents/pymc-unified-platform-spec/pymc-marketing-mcp/src/marketing_mcp/errors.py)
* `tests/unit/test_hard_test_remediation.py`: Lineage regression test suite
* `tests/unit/test_adversarial_torture_suite.py`: Adversarial lineage torture tests
