# Lesson 51: Resource-Bound Recovery and Disconnect Lifecycle Reset

### Context
Agent Skillpack trace evaluation (`src/marketing_mcp/skillpack/evals.py`) and job execution resilience under transient network disconnects, worker crashes, and server restarts.

### What happened
During hardening of PR #35 (`feat/retest-remediation-and-heavy-async-resilience`), the evaluation harness authorized recovery resumption (`resume_job`) or job resubmission based solely on whether `rec_job_type` matched the tool family of `last_submitted_async_tool`. It did not check `job_id`. Code review revealed that if Job A was interrupted, a recovery step returning unrelated Job B would be authorized to resume or resubmit against Job B.

Furthermore, `disconnected` remained `True` indefinitely after recovery, falsely blocking subsequent valid async submissions later in the session.

### Observable symptom
Code review finding on PR #35:
```text
Recovery authorization is still not tied to the same interrupted submission instance.
Current logic can conceptually allow:
submit_fit_mmm_job # interrupted job A disconnect
recover_execution_state -> returns failed budget job B
submit_budget_optimization_job # accepted!
```

Additionally, in valid multi-step workflows with recovery:
```text
unauthorized resubmission without preceding recovery after disconnect: tool 'submit_cross_validate_mmm_job'
```
Even after `resume_job` had succeeded and the model was diagnosed, subsequent async submissions were blocked because the `disconnected` flag leaked past the recovery cycle.

### Impact
- **Security & Multi-Tenancy**: An agent could resume or resubmit against an incorrect job state, leaking cross-job data or executing operations against mismatched resources.
- **Correctness & Reliability**: False positive rejections blocked legitimate multi-job workflows after a single recovery cycle completed.

### Incorrect assumption
Assumed that matching the job family (`job_type`) was sufficient to prove recovery identity, and assumed a disconnect was an end-of-trace event that did not require explicit state machine exit upon successful resumption.

### Root cause
**Confirmed**.
1. `evaluate_tool_trace` recorded `last_submitted_async_tool` but did not extract or track `last_submitted_async_job_id`.
2. The recovery validation branch did not enforce `rec_job_id == last_submitted_async_job_id`.
3. `evaluate_tool_trace` had no state exit transition to reset `disconnected = False` and clear `last_recovery = None` when a valid resume or resubmission was performed or when continuation tools executed on usable results.

### Why the architecture allowed it
The evaluator state was modelled as loose boolean flags (`disconnected = True`) rather than an explicit finite state machine with defined entry, transition, and exit conditions.

### Fix
1. Extracted `sub_job_id` from submit step results or arguments, binding `last_submitted_async_job_id`.
2. Enforced strict equality: `rec_job_id == last_submitted_async_job_id`, failing closed if either was missing, empty, or mismatched.
3. Enforced fail-closed rejection for unknown `job_type` not present in `JOB_TYPE_TO_SUBMIT_TOOL`.
4. Reset `disconnected = False` and `last_recovery = None` upon successful `resume_job` or authorized same-family resubmission, and cleared disconnect context when continuation tools (`diagnose_mmm`, `inspect_dataset`, `optimize_budget`) execute after `has_usable_result: true`.

```python
# In src/marketing_mcp/skillpack/evals.py
if not last_submitted_async_job_id:
    reasons.append(
        f"recover_execution_state at step {index} cannot match recovered job '{rec_job_id}' "
        "because preceding async submission did not record an authoritative 'job_id'"
    )
elif job_id_valid and rec_job_id != last_submitted_async_job_id:
    reasons.append(
        f"recovery resource mismatch: recover_execution_state at step {index} recovered "
        f"job '{rec_job_id}' but originating submission was for job '{last_submitted_async_job_id}'"
    )

# Valid authorized resume closes recovery/disconnect context
if valid_resume_authorized:
    disconnected = False
    last_recovery = None
```

### Verification
- `tests/unit/test_skill_pack_contract.py::test_evaluator_rejects_recovery_with_mismatched_job_id`
- `tests/unit/test_skill_pack_contract.py::test_evaluator_rejects_recovery_with_missing_job_id`
- `tests/unit/test_skill_pack_contract.py::test_evaluator_rejects_recovery_with_unknown_job_type`
- `tests/unit/test_skill_pack_contract.py::test_evaluator_resets_disconnect_state_after_valid_resume`
- `tests/unit/test_skill_pack_contract.py::test_evaluator_resets_disconnect_state_after_valid_resubmit`
- All 25 evaluation traces in `evals.json` pass without errors.

### Prevention rule
> **Always bind state recovery authorization to the concrete resource instance ID (`job_id`) and family; never infer resource identity from type alone, and always define explicit exit transitions that reset lifecycle flags when a recovery cycle completes.**

### Reusable lesson
Finite state machines in evaluators and supervisors must model resource identity explicitly and clear transitional context upon cycle completion. Unbound resource recovery is a critical vulnerability in autonomous agent workflows.

### Related code
- `src/marketing_mcp/skillpack/evals.py`
- `src/marketing_mcp/jobs/service.py`

### Related tests
- `tests/unit/test_skill_pack_contract.py`

### Status
Solved (commit `f2450eb`, merged in `69f6280`)
