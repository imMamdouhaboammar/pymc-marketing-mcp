# PyMC Failure-Lesson Schema & Authoring Guide

Every entry in `Failure-lessons/` represents a durable post-mortem and invariant definition. Follow this strict schema for all new lessons (`Failure-lessons/<NN>-<kebab-case-slug>.md`).

---

## Canonical Markdown Schema

```markdown
# Lesson {NUMBER}: {Descriptive Title Focused on Failure Mechanism}

### Context
{Where this problem appeared: module, boundary, endpoint, workflow, or environment.}

### What happened
{Factual chronological description of the breakdown.}

### Why it mattered / Impact
{Specific risk to correctness, statistical integrity, multi-tenancy, security, reliability, or performance.}

### Observable symptom
{Exact user-visible or engine-visible symptom: HTTP status, traceback, divergence, corrupted metric, or test failure.}

### Incorrect assumption
{What the system, contract, or engineer falsely assumed to be true.}

### Root cause
{Classification: Confirmed | Strongly indicated | Open hypothesis | Unknown}
{Technical explanation of the precise failure mechanism with evidence.}

### Why the system allowed it
{The systemic gap: missing preflight validator, deficient test mock, implicit contract, or architectural boundary leak.}

### Fix
1. {Step 1: architectural or domain fix}
2. {Step 2: boundary validation or synchronization}
3. {Step 3: test or invariant enforcement}

### Verification
{Concrete test command, fixture, or adversarial experiment that proved the fix works.}

### Prevention rule
> **{One crisp, non-negotiable invariant that prevents future recurrence.}**

### Reusable lesson
{Where else this principle or failure class applies across the monorepo.}

### Related code
- `{stable module or file path 1}`
- `{stable module or file path 2}`

### Related tests
- `{reproduction test path 1}`
- `{boundary or property test path 2}`

### Related lessons
- [{NN-other-lesson.md}](./{NN-other-lesson.md})

### Status
{Resolved | Partially mitigated | Unresolved | Superseded}
```

---

## Detailed Section Requirements

### 1. Title & Numbering
- Must follow the sequential pattern: `<NN>-<kebab-slug>.md` (e.g. `65-mcmc-memory-leak-in-streaming-traces.md`).
- Title must focus on the **failure mechanism**, never on a ticket number or person (e.g. "Unvalidated Financial Assumptions in Decision Builders", NOT "Fix for bug #123").

### 2. Context & Root Cause Grounding
- Must distinguish between:
  - **Confirmed**: Root cause proven by reproducing the bug with a failing test and observing the exact code branch.
  - **Strongly indicated**: Evidence points to this cause, but concurrency or runtime non-determinism prevents 100% isolation.
  - **Open hypothesis**: Symptom observed, but root cause is still speculative.
  - **Unknown**: Anomaly detected without verified causal explanation.
- **Never claim an open hypothesis as confirmed fact.**

### 3. Prevention Rule ("Rules We Now Enforce")
- The prevention rule must be an enduring, generalizable invariant.
- Bad: "Remember to call validate() in ledger.py".
- Good: "Every domain builder consuming contracts with deferred validation methods (`validate()`) must explicitly invoke and assert validity at the boundary before executing downstream calculations."

### 4. Code & Test Grounding
- All file paths in `Related code` and `Related tests` must exist in the repository tree.
- Regression tests must be tested for **falsification**: if the fix is temporarily commented out or reverted, the regression test must fail (RED). If it still passes, the test does not actually protect against the failure.

### 5. Status Protocol
- **Resolved**: Fix implemented, tested with verified regression coverage, and merged to main.
- **Partially mitigated**: Defense-in-depth added or preflight checks added, but underlying runtime limitation remains open.
- **Unresolved**: Failure documented as a known hazard pending architectural refactor.
- **Superseded**: Replaced by a newer lesson or platform architecture.
