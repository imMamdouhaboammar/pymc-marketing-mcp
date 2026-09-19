---
name: pymc-job-resilience
version: 1.1.0
description: Use when long-running asynchronous compute jobs (fitting, transform, budget optimization, flighting, cross-validation, prior sensitivity) time out, disconnect, need progress/status, recovery, resume, cancellation, or duplicate-submission avoidance.
---

# PyMC Job Resilience

Use this skill to manage all asynchronous compute operations across the six supported job families:
1. **Model Fitting**: `submit_fit_mmm_job`
2. **Data Transformation**: `submit_transform_ad_export_job`
3. **Budget Optimization**: `submit_budget_optimization_job`
4. **Flighting Optimization**: `submit_flighting_optimization_job`
5. **Cross-Validation**: `submit_cross_validate_mmm_job`
6. **Prior Sensitivity**: `submit_prior_sensitivity_job`

All jobs are persisted server-side with fenced leases, monotonic attempt counters, and staged execution checkpoints.

## Start and observe

1. Submit the appropriate asynchronous job using its dedicated submit tool and retain the returned `job_id` (and optional `idempotency_key`).
2. Use `get_job_status` for a direct state check or `poll_job_progress` for a bounded server heartbeat. Do not build rapid, unbounded polling loops; respect the tool timeout/state and wait for the client's next normal interaction before another poll when no progress occurs.
3. Terminal states are authoritative:
   - If `succeeded`, extract the job result payload and follow the type-specific continuation action.
   - If `failed` or `cancelled`, preserve the recorded error and state rather than fabricating artificial results.

## Type-specific continuation actions

- **Model Fitting (`fit_mmm`)**: Extract `model_id`. Confirm persisted model state and run `diagnose_mmm` before any decision-grade use (`pymc-diagnostics-gate`).
- **Data Transformation (`transform_ad_export`)**: Extract `transformed_dataset_id`. Proceed with `inspect_dataset` or `validate_dataset` (`pymc-dataset-readiness`).
- **Budget Optimization (`budget_optimize`)**: Extract `scenario_id` and recommended allocations. Proceed to `simulate_budget` or scenario evaluation (`pymc-budget-optimization`).
- **Flighting Optimization (`flighting_optimize`)**: Extract `scenario_id` and weekly flighting schedule. Review channel flighting patterns and simulation outcomes.
- **Cross-Validation (`cross_validate_mmm`)**: Extract predictive error metrics (e.g. RMSE, MAPE) and stability findings. If predictive failure is detected, review dataset quality before modeling.
- **Prior Sensitivity (`prior_sensitivity`)**: Extract adstock/saturation sensitivity metrics and channel ranking stability. Proceed to `calibrate_mmm` or `recommend_next_measurement`.

## Disconnect and failure recovery

When client connection is interrupted, **never immediately resubmit the expensive compute**:
1. First inspect or list existing jobs, then call `recover_execution_state` with `job_id_or_key`.
2. Evaluate the returned recovery payload:
   - `can_resume=true`: Call `resume_job(job_id)`. If a completed checkpoint is recorded, the job is restored to `succeeded` with its result without re-executing. Otherwise, it is requeued with a refreshed execution generation.
   - `has_usable_result=true`: Read the completed result directly.
   - `status="running"`: The worker lease is active; continue with `poll_job_progress`.
3. Resubmission is permitted only when authoritative recovery returns a terminal `failed` or `cancelled` state with `can_resume=false` and `has_usable_result=false`.
4. Use `cancel_job` only when cancellation is explicitly requested. Cooperative cancellation safely halts execution before output persistence or side-effect registration.

