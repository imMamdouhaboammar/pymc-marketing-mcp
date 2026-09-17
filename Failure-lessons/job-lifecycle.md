# Failure Lessons: Job Lifecycle & Async State Machine Guarantees

This document captures durable failure lessons, root causes, and architectural invariants for asynchronous compute jobs, state transitions, cooperative cancellation fencing, and payload efficiency in `pymc-marketing-mcp`.

---

## JOB-001: Infinite `cancelling` State & Orphan Compute Fences

### What happened
When a client requested cancellation of a long-running MCMC model fitting job via `cancel_job`, the job status changed from `running` to `cancelling`. However, the job remained stuck in `cancelling` permanently. The underlying compute process continued running at 100% CPU utilization until MCMC sampling finished 15 minutes later, at which point the worker marked the job as `completed`, completely overwriting the cancellation request!

### Why it mattered
* **Runaway Compute & Resource Starvation**: Bayesian MCMC sampling consumes significant CPU and GPU capacity. In multi-tenant environments, orphan jobs starve queued jobs of compute resources and generate runaway cloud compute bills.
* **State Machine Incoherence**: A client that cancelled a job later observed that the job transitioned to `completed`, creating severe ambiguity about whether the model was valid, safe to deploy, or billed.

### Observable symptom
* Job status stuck in `cancelling` for indefinite durations.
* Worker logs continued printing NUTS progress bars (`1200/2000 iterations`).
* Late `completed` event emitted long after client issued `cancel_job`.

### Initial assumption
Developers assumed:
1. Setting `job.status = "cancelling"` in the database would automatically stop execution.
2. Standard Python thread pools support external termination of native C-extensions.

### Root cause
* **Status**: Confirmed.
* **Thread Interruption Inability**: Python threads executing native C/C++ or PyTensor computational graphs cannot be asynchronously interrupted from external code via thread signals.
* **Absence of Cooperative Checkpoints**: The inner sampling loop had no cancellation token inspection between iterations.
* **Missing State Machine Terminalization**: `cancelling` was modeled as a durable state rather than an ephemeral transition, with no timeout or terminal guarantee.
* **Late Result Race Condition**: The worker's completion handler blindly wrote `status = "completed"` at the end of the run without checking whether the job status had mutated to `CANCELLED` during execution.

### Why the system allowed it
The job executor lacked cooperative token propagation, atomic state transition validation, and late-result fencing.

### Fix
1. **Strict Finite State Machine**: Defined permissible transitions:
   ```text
   QUEUED ────> RUNNING ────> SUCCEEDED
     │            │
     │            ├─────────> FAILED
     │            │
     └────────────┴─────────> CANCELLED
   ```
2. **Immediate Queue Cancellation**: Jobs in `QUEUED` transition directly to `CANCELLED` without entering intermediate states.
3. **Cooperative Cancellation Token**: Workers periodically inspect `cancellation_token.is_cancelled()` at atomic checkpoint boundaries (e.g., chain initialization, sample batches).
4. **Late-Result Fencing**: In the worker completion handler, state updates use optimistic locking / conditional writes:
   $$\text{UPDATE jobs SET status = 'SUCCEEDED' WHERE id = :id AND status = 'RUNNING'}$$
   If the job is already `CANCELLED`, the worker discards results and releases resources immediately.
5. **Idempotent Cancellation**: Invoking `cancel_job` on a terminal job (`CANCELLED`, `SUCCEEDED`, `FAILED`) is an idempotent no-op that returns the existing status.

### Verification
* `tests/unit/test_job_state_machine.py`: Verifies state machine transitions, illegal transitions, and idempotency.
* `tests/unit/test_hard_test_remediation.py::test_job_cancellation_fencing_and_idempotency`: Verifies cooperative fencing and late-result rejection.

### Prevention rule
> **Rule**: Transitional states must never become indefinite durable states. State machines must guarantee eventual transition to a terminal state. Late worker completions must be fenced and discarded if a job was cancelled.

### Reusable lesson
Every asynchronous job engine executing long-running native computation must combine cooperative polling tokens with database-level conditional writes to fence against late worker results.

### Related failures
* [Failure Lesson 10: State Machine Crash Recovery & Resumption](./10-state-recovery-and-crash-resumption.md)
* [Failure Lesson 21: Deceptive Async Job Checkpoints](./21-deceptive-async-job-checkpoints.md)
* [Failure Lesson 32: Deceptive Cancellation & Orphan Compute Fences](./32-deceptive-cancellation-and-orphan-compute-fence.md)

---

## JOB-002: Unbounded List Operations Payload Bloat & Context Overflow

### What happened
As a test suite or production tenant accumulated 20–50 completed jobs, invoking `list_jobs` resulted in multi-megabyte JSON responses (>5MB, >100,000 tokens). This caused LLM client agents to crash with context window overflow errors and increased endpoint latency from 25ms to >12 seconds.

### Why it mattered
* **Agent Failure**: Autonomous AI agents communicating over MCP cannot process single tool responses exceeding context limits.
* **Egress & Latency Penalty**: Serialization of tens of thousands of posterior diagnostics per job saturated server memory and network bandwidth.

### Observable symptom
* `list_jobs` tool calls failing in AI agent clients with `ContextWindowExceededError` or JSON parse timeouts.
* Heavy server CPU usage during JSON serialization of `list_jobs`.

### Initial assumption
Developers assumed it was convenient to return the complete `JobRecord` dataclass (including serialized convergence summaries, channel parameters, error traces, and input snapshots) for every job in `list_jobs`.

### Root cause
* **Status**: Confirmed.
* Monolithic data retrieval. No separation existed between summary list views and detailed resource inspection views.

### Why the system allowed it
The API schema did not enforce pagination, field projection, or detail-level controls on collection endpoints.

### Fix
1. **Lightweight Default Projections**: `list_jobs` defaults to `verbose=False`, returning only compact identity and lifecycle fields:
   - `job_id`, `status`, `job_type`, `created_at`, `duration_seconds`
2. **Explicit Detail Opt-In**: Full diagnostics, logs, and trace metrics require calling `get_job(job_id=..., verbose=True)`.
3. **Payload Compression**: Connected edge summaries that cap list items to $<500$ bytes each.

### Verification
* `tests/unit/test_adversarial_torture_suite.py::test_list_jobs_payload_compactness`
* Asserts that `list_jobs` with 50 completed jobs returns $<50$ KB total payload size with `verbose=False`.

### Prevention rule
> **Rule**: Collection and list endpoints must default to compact summary schemas. Heavy diagnostic traces and payload snapshots must require explicit single-resource queries.

### Reusable lesson
Always design API response envelopes with token budget economics in mind. Autonomous AI agents require concise, high-density responses.

---

## Protected Systems & Code References

* `src/marketing_mcp/jobs/models.py`: Job state machine definitions and transition guards
* `src/marketing_mcp/jobs/service.py`: Job service and state management
* `src/marketing_mcp/jobs/executor.py`: Worker execution and cooperative cancellation fencing
* `src/marketing_mcp/mcp/tools/jobs.py`: MCP tool endpoints for job control and compact list queries
* `tests/unit/test_job_state_machine.py`: 12 state transition unit tests
