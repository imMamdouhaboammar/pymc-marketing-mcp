# Lesson 63: Fallback Response Fabrication in Cohort Accounting

### Context
Media spend cohort decomposition in `build_media_response_cohort_ledger` (`src/marketing_mcp/domain/cohorts/ledger.py`).

### What happened
When constructing `MediaResponseCohortLedger` from caller-supplied `spend_records`, the builder implemented several permissive fallback defaults:
1. When neither `total_response` nor `channel_response_rates[ch]` was provided, the builder executed:
   ```python
   tot_resp = spend
   ```
   silently assuming a 1:1 conversion rate from spend currency to response units.
2. When a channel was not found in `adstock_weights`, it defaulted to:
   ```python
   raw_weights = adstock_weights.get(ch, [1.0])
   ```
   treating unknown channels as instantaneous impulses with zero carryover decay.
3. When weights were empty or non-positive, it used:
   ```python
   total_w = sum(raw_weights) or 1.0
   ```
   masking corrupt or inverted weight vectors.
4. Duplicate `(source_period, channel)` pairs were accepted without error, overwriting or creating duplicate cohorts with identical keys.

### Why it mattered / Impact
Silently equating response to spend ($1:1$) fabricates outcomes without econometric or experimental basis. A channel with \$10,000 spend would be reported as generating 10,000 conversions or units of response simply because the caller omitted the parameter. Defaulting missing adstock weights to $[1.0]$ wipes out carryover effects, destroying the very purpose of cohort accounting (which is tracking carryover realizations over time).

### Observable symptom
An external automated code review (Cubic) flagged that omitting response inputs produced plausible financial metrics (gross revenue, profit, ROAS) derived entirely from fabricated response counts rather than failing closed.

### Incorrect assumption
Assumed permissive fallbacks provided caller convenience during exploratory analysis or rapid prototyping.

### Root cause
**Confirmed**. Permissive default assignment in analytical domain builders violates the core platform invariant: **Fail-Closed Statistical Integrity**. Scientific models must never invent empirical outcomes when data is missing.

### Why the system allowed it
The ledger builder was initially written as a helper utility rather than an authoritative domain gateway, prioritizing execution completion over strict input validation.

### Fix
1. **Require Response Specification**: Explicitly verify that either `total_response` or `channel_response_rates[ch]` is provided; raise `DomainError("INPUT_INVALID", ...)` otherwise.
2. **Fail-Closed Adstock Weights**: Require `ch in adstock_weights`; raise `DomainError("INPUT_INVALID", ...)` if missing.
3. **Weight Vector Validation**: Reject empty, negative, or sum $\le 0$ adstock decay weights.
4. **Duplicate Cohort Prevention**: Track `seen_cohorts` and reject duplicate `(source_period, channel)` records.
5. **Non-Negativity Assertions**: Reject negative spend and negative response values.

### Verification
Added 4 negative test cases in `tests/unit/test_cohort_ledger.py`:
- `test_reject_missing_response_and_rate`
- `test_reject_channel_not_in_adstock_weights`
- `test_reject_invalid_adstock_weights`
- `test_reject_duplicate_cohort_records`

### Prevention rule
> **Never fabricate scientific, physical, or economic outcomes via fallback defaults. If empirical outcome data, response rates, or adstock decay vectors are missing, fail closed at the domain boundary with an actionable error diagnostic.**

### Reusable lesson
Applies across all service builders, adapters, and parameter parsers in the platform. When optional parameters represent critical scientific quantities, their absence must trigger an explicit error or require an explicit user acknowledgment, never a silent 1:1 default.

### Related code
- `src/marketing_mcp/domain/cohorts/ledger.py`
- `src/marketing_mcp/domain/cohorts/contracts.py`

### Related tests
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger::test_reject_missing_response_and_rate`
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger::test_reject_channel_not_in_adstock_weights`
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger::test_reject_invalid_adstock_weights`
- `tests/unit/test_cohort_ledger.py::TestMediaResponseCohortLedger::test_reject_duplicate_cohort_records`

### Related lessons
- [28-statistical-authority-duplication-and-fallback-attribute-error.md](./28-statistical-authority-duplication-and-fallback-attribute-error.md)
- [46-bogus-provenance-acceptance-on-uncalibrated-confidence.md](./46-bogus-provenance-acceptance-on-uncalibrated-confidence.md)
- [48-registry-negative-guards-and-rfc-gated-objectives.md](./48-registry-negative-guards-and-rfc-gated-objectives.md)

### Status
Resolved
