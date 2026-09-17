---
name: pymc-job-resilience
version: 1.0.0
description: Use when a long-running fit times out, disconnects, needs progress/status, recovery, resume, cancellation, or duplicate-submission avoidance.
---

# PyMC Job Resilience

Use this for long-running or interrupted MMM fitting. Current repository jobs are persisted server-side with recovery helpers, but several recovery/polling capabilities remain experimental and the architecture must not be described as an external durable worker system.

## Start and observe

1. Use `submit_fit_mmm_job` when asynchronous fitting is appropriate and retain the returned `job_id`.
2. Use `get_job_status` for a direct state check or `poll_job_progress` for a bounded server heartbeat. Do not build rapid, unbounded polling loops; respect the tool timeout/state and wait for the client’s next normal interaction before another poll when no progress occurs.
3. Terminal states are authoritative. If completed, continue with the resulting model ID. If failed/cancelled, preserve the error/state instead of fabricating a model result.

## Disconnect recovery

When the client loses its connection, **do not immediately resubmit the expensive fit**. First inspect/list the existing job, then `recover_execution_state`. Use `resume_job` only when the returned lifecycle state permits resumption and a valid checkpoint exists. Resubmission is a last resort only when authoritative recovery returns a terminal `failed`/`cancelled` state with `can_resume=false` and `has_usable_result=false`. Active, recoverable, successful, or unavailable state is not permission to submit a duplicate fit.

Use `cancel_job` only on a queued/running job when cancellation is actually requested. After a recovered/completed fit, confirm the persisted model state and run `diagnose_mmm` before any decision-grade use.
