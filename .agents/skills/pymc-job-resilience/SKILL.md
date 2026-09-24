---
name: pymc-job-resilience
version: 2.0.0
description: Use when long-running asynchronous compute jobs (fitting, transform, budget optimization, flighting, cross-validation, prior sensitivity) time out, disconnect, need progress/status, recovery, resume, cancellation, or duplicate-submission avoidance.
---
# PyMC Job Resilience

Keeps expensive work alive across timeouts and disconnects. MCMC fits and validation runs take minutes; remote clients drop long requests. Background jobs are persisted server-side with checkpoints, so the agent can always find, watch, recover, or resume them instead of paying for the same sampling twice.

## Job families

| Work | Submit tool | Payload | Result to extract | Continue with |
| --- | --- | --- | --- | --- |
| MMM fit | `submit_fit_mmm_job` | `config` (same as `fit_mmm`) | `model_id` | `diagnose_mmm` (`pymc-diagnostics-gate`) |
| Ad-export reshape | `submit_transform_ad_export_job` | flat args (same as `transform_ad_export`) | `transformed_dataset_id`, `spend_reconciled` | `inspect_dataset`, `validate_dataset` |
| Static budget split | `submit_budget_optimization_job` | `config` (same as `optimize_budget`) | recommended allocation, `scenario_id` | present, or `simulate_budget` variants |
| Weekly flighting | `submit_flighting_optimization_job` | `config` (same as `optimize_flighting`) | weekly schedule, `scenario_id` | present with warnings |
| Cross-validation | `submit_cross_validate_mmm_job` | `input` (same as `cross_validate_mmm`) | error metrics, stability findings | `pymc-model-validation` |
| Prior sensitivity | `submit_prior_sensitivity_job` | `input` (same as `evaluate_prior_sensitivity`) | sensitivity findings | `calibrate_mmm` or `recommend_next_measurement` |

Every submit tool also takes `idempotency_key`. Budget and flighting jobs still pass through the decision gate when they run.

## Submit

- Build the key from the complete input: `"<dataset_id>:fit:<config hash>"`, `"<model_id>:cv:<config hash>"`, `"<model_id>:opt:<config hash>"`, where the hash is the first 12 hex characters of a SHA-256 of the canonical JSON payload.
- The server matches on the key alone. Same key returns the existing job; change the key whenever the inputs change.
- Record `job_id` and the key in the ID ledger immediately, and tell the user both: they are how the work is found again after a disconnect.

## Watch

1. `poll_job_progress(job_id, timeout_seconds=25)` waits server-side (capped at 60 seconds) and returns `job`, `latest_checkpoint`, `is_terminal`, `elapsed_seconds`, and `timed_out`.
2. Make at most **three consecutive polls** without a new checkpoint stage. Then stop, report the job ID and stage ("sampling_initialized, about 30%"), and pick up again on the user's next message.
3. `get_job_status(job_id)` is a single instant read; use it when you only need the current state.
4. Statuses: `queued`, `running`, `cancelling`, `succeeded`, `failed`, `cancelled`. The last three are terminal.

On `succeeded`, extract the result and continue per the table above. On `failed` or `cancelled`, report the recorded `error` as it is; never fill the gap with invented results.

## After a disconnect or restart

Never resubmit expensive work first. Recover:

1. If you lost the `job_id`, call `list_jobs(status="running", limit=20)` or pass the `idempotency_key` directly to recovery.
2. `recover_execution_state(job_id_or_key="<job_id or idempotency_key>")` returns `status`, `can_resume`, `has_usable_result`, `checkpoint_count`, `latest_checkpoint`, `result`, `error`, and `recommended_action`.
3. Act on the flags:
   - `status: "succeeded"` with a non-empty `result`: read `result` and continue; no rerun needed.
   - `status: "failed"` or `"cancelled"`: do not continue from `has_usable_result` alone. The server can set that flag from a completed checkpoint on a job that later failed. Use `can_resume`, or report `error`.
   - `status: "running"` or `"queued"`: keep watching with `poll_job_progress`.
   - `can_resume: true`: `resume_job(job_id)`. If a completed checkpoint exists, the job is restored to `succeeded` with its result; otherwise the unfinished stage restarts (sampling restarts from the beginning of that stage).
   - All false and status `failed` or `cancelled`: only now may you resubmit, and only after telling the user why the previous attempt ended.

## Cancel

`cancel_job(job_id)` only when the user asks. Cancellation stops the job before it persists outputs. Confirm the terminal state with `get_job_status` before reporting it done.

## Talking to the user about long work

- Set expectations once: "The model is sampling on the server; this usually takes several minutes. Job ID `job-...`."
- Report progress using the checkpoint stage name and any progress value the server returns.
- If the user leaves and returns, start with `recover_execution_state` before any new submission.

## Stop conditions

Stop when the job is not found or belongs to another tenant (`JOB_NOT_FOUND`, `AUTH_FORBIDDEN`), when recovery says the job cannot resume and has no result and the user has not approved a resubmission, or when the job failed for a data or model reason (route that to the owning skill).
