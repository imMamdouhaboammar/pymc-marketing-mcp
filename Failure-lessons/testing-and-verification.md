# Failure Lessons: Testing Strategy & Adversarial Verification

This document captures durable engineering principles, testing anti-patterns, adversarial test fixtures, and falsification protocols discovered while hardening `pymc-marketing-mcp`.

---

## 1. The Cardinal Testing Axiom

> **A regression test is not proven useful until it can be shown to fail when the relevant fix is removed or the defect is reintroduced.**
>
> $$\text{Green Tests} \ne \text{Verified Requirements}$$

Throughout this hardening mission, the most severe bugs in the platform were guarded by passing test suites. The tests were green, yet the software failed catastrophically in production because the assertions verified structural incidental details rather than economic, statistical, or operational invariants.

---

## 2. Testing Anti-Patterns Discovered

### Anti-Pattern 1: Shape-Only Assertions (The Flighting Optimizer Mask)
* **What Happened**: The original test for `optimize_flighting` asserted:
  ```python
  assert len(schedule) == 8
  assert pytest.approx(sum(row["spend"] for row in schedule)) == 10000.0
  ```
  Both assertions passed with flying colors.
* **Why It Was Deceptive**: The optimizer was completely broken! Due to float64 gradient underflow at iteration 0, it returned an unoptimized, flat 25% equal allocation across all 4 channels ($312,500/channel/week for 8 weeks).
* **Lesson**: An optimizer test that only asserts output shape and constraint satisfaction does not test optimization. It tests array formatting. Always assert **economic sensitivity and asymmetry**.

### Anti-Pattern 2: Permissive Happy-Path Boundary Tests (The CLV Lineage Leak)
* **What Happened**: Tests for multi-model CLV verified that supplying matching models worked. They never supplied two models with identical customer IDs but different dataset fingerprints, different currencies, or missing metadata.
* **Why It Was Deceptive**: Because the guard was written as `if p_fp and v_fp and p_fp != v_fp: reject`, any model fixture with `None` or omitted fingerprints silently bypassed the check.
* **Lesson**: A security or lineage guard is only as strong as its fail-closed negative tests. You must assert rejection when metadata is omitted, partial, or maliciously malformed.

### Anti-Pattern 3: Mocked Component Leakage (The Validation Parity Illusion)
* **What Happened**: Tests for `submit_fit_mmm_job` mocked out the dataset ingestion layer. The test asserted that `job_service.enqueue_job` was called.
* **Why It Was Deceptive**: In the real application, `submit_fit_mmm_job` bypassed `DatasetValidator` entirely, enqueuing invalid data that crashed the background worker minutes later.
* **Lesson**: Never mock the subsystem being tested. End-to-end admission tests must feed un-mocked invalid payloads to the submission perimeter and verify immediate synchronous rejection.

### Anti-Pattern 4: Single-Instance Scale Bias (The $10k Stagnation Trap)
* **What Happened**: All existing optimization tests used small synthetic budgets ($5,000 or $10,000). At these small numbers, raw dollar variables did not suffer from float64 underflow.
* **Why It Was Deceptive**: Real enterprise marketing budgets are $1,000,000 to $50,000,000. At $10M, SciPy's finite-difference step $\Delta x \approx 1.49 \times 10^{-8}$ underflows machine precision ($10^7 + 10^{-8} = 10^7$).
* **Lesson**: Numerical algorithms must be stress-tested across the full dynamic range of real-world inputs ($10^2, 10^4, 10^6, 10^8$).

### Anti-Pattern 5: The Phantom Calculation (Unasserted Test Variables)
* **What Happened**: In `test_flighting_respects_conservation_floors_and_caps`, the test computed `total_budget = sum(r["spend"] for r in schedule)` but omitted the `assert` statement comparing it to the target budget.
* **Why It Was Deceptive**: The test passed green and appeared to test budget conservation during code reviews. In reality, Python computed the value and silently discarded it without checking the invariant.
* **Lesson**: Enforce linter rule `F841` (unused variables) across all test directories, and audit all tests to guarantee every intermediate invariant calculation has an explicit, tight tolerance assertion.

### Anti-Pattern 6: Architectural Claims Without Runtime Assertions
* **What Happened**: Early architecture documentation claimed "SIMD hardware SHA-256 acceleration" and "pure native zero-copy streaming" for the Rust MCP interaction engine.
* **Why It Was Deceptive**: The actual code used standard library hashing and standard buffered IPC channels; no SIMD intrinsics or unbuffered streaming existed in the runtime path.
* **Lesson**: Architectural claims must be verified via actual runtime assertions, hardware telemetry, and automated throughput benchmarks before documentation is committed.

---

## 3. Reusable Adversarial Test Fixtures

To ensure permanent regression prevention, the repository now employs six standardized adversarial fixture classes:

### 1. Known-Effect MMM Fixtures
* **Design**: Synthetic datasets generated with known ground-truth saturation parameters where Channel A has $3\times$ higher marginal response ($\alpha_A = 3.0$) than Channel B ($\alpha_B = 1.0$).
* **Assertion**: The optimizer must allocate strictly more budget to Channel A than Channel B:
  ```python
  assert allocation["Channel_A"] > 1.5 * allocation["Channel_B"]
  ```

### 2. Reversed-Effect Fixtures
* **Design**: Invert channel parameters ($\alpha_A = 1.0, \alpha_B = 3.0$).
* **Assertion**: The optimizer must invert its allocation ranking, proving it is responding dynamically to the posterior surface rather than hardcoded biases.

### 3. Scale Stress Torture Fixtures
* **Design**: Run the exact same optimization across total budgets of $100, $10,000, $1,000,000, and $10,000,000.
* **Assertion**: All budgets must converge with non-zero gradient descent iterations and preserve relative channel priority.

### 4. Same-ID / Disjoint-Cohort CLV Fixtures
* **Design**: Two datasets containing identical customer IDs (`user_001` through `user_100`) but with divergent transaction histories, different observation windows (2022 vs 2024), or different currencies (USD vs EUR).
* **Assertion**: Multi-model composition must raise `ModelLineageError("DATASET_MISMATCH")` or `ModelLineageError("CURRENCY_MISMATCH")`.

### 5. Zero-Support Sparse Panel Fixtures
* **Design**: Multi-region panel data where specific channels have exactly zero spend in certain geographies.
* **Assertion**: Response curve generators and budget optimizers must tag these cells as `no_empirical_support` or `prior_dominated` and emit explicit risk warnings.

### 6. State-Machine Lifecycle Torture
* **Design**: Inject asynchronous cancellations on queued, running, already-cancelled, and finished jobs. Send late worker completion payloads after cancellation.
* **Assertion**: The state machine must reject invalid transitions, discard late results, maintain idempotency, and never linger in transitional states.

---

## 4. The Mandatory Red-Green Verification Protocol

Before declaring any bug resolved or submitting code, every agent must follow this protocol:

1. **Step 1: Author the Failing Adversarial Test (RED)**
   Write a test that specifically targets the defect or invariant. Run it against the unfixed code and verify that it **fails with the exact expected failure signature**.
2. **Step 2: Implement the Minimal Working Diff**
   Fix the root cause at the proper abstraction level.
3. **Step 3: Verify Test Passes (GREEN)**
   Run the test and verify that it passes cleanly.
4. **Step 4: Re-introduce the Defect (Falsification Check)**
   Temporarily revert the fix or comment out the guard. Run the test again. If the test still passes, **the test is invalid and must be rewritten**.

---

## 5. Repository Verification Suites

| Test Suite | Purpose | Tests |
|---|---|---|
| `tests/unit/test_hard_test_remediation.py` | Targeted regression tests for P0/P1 remediation findings | 13 passed |
| `tests/unit/test_flighting_domain.py` | Budget flighting domain invariants, simplex scaling, multi-start | 21 passed |
| `tests/statistical/test_flighting_optimization.py` | End-to-end NUTS MCMC statistical flighting verification | 2 passed |
| `tests/unit/test_adversarial_torture_suite.py` | Aggressive adversarial edge-case torture suite | 22 passed |
| `tests/unit/test_job_state_machine.py` | Asynchronous job state transitions and cancellation fencing | 12 passed |
| `tests/unit/test_error_normalization.py` | Error code taxonomy and user-actionable envelope parity | 8 passed |
| `tests/unit/test_action_runtime_policy.py` | Tool registry AST alignment and next_actions validation | 7 passed |
| `tests/benchmarks/benchmark_engine.py` | Multi-scenario native vs Python engine throughput benchmark | 7 scenarios |
| `tests/unit/test_request_safety.py` | Safety middleware rate limiting and configurable threshold verification | 5 passed |
| `tests/unit/test_native_parity.py` | Parity verification between native Rust and Python fallback engines | 8 passed |

