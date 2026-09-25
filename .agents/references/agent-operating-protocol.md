# Agent Operating Protocol

How an LLM agent drives the PyMC Marketing MCP server across a whole session: which call comes first, how to read every result, how to keep IDs straight, when to use background jobs, and how to recover from each error code. Skills tell you *what* workflow to run; this protocol tells you *how* to operate the server while running it.

## 1. Session bootstrap

Run these before you create anything new. The server is persistent and multi-session: a previous conversation, or the same conversation before a disconnect, may already have registered the dataset, started the fit, or approved the model.

1. **Load guidance once.** Call `get_skill_guidance(task="<the user's request, verbatim>")`. The result names the routed skill and inlines its guidance, so one call is enough. If your host exposes MCP resources, `marketing://skills/{skill_name}` returns the same text.
2. **Look before you build.** Call `list_datasets` when data is involved and `list_jobs(limit=10)` when a fit, optimization, or validation may already be running. Reuse what exists; ask the user when two candidates look equally plausible.
3. **Confirm model identity.** When the user mentions a model, call `get_model_status(model_id)` before any downstream step. Treat a model ID you remember from another session as unverified until the server confirms it.

Skip steps 2 and 3 only for pure explanation questions that need no server state.

## 2. Reading the result envelope

Every successful tool call returns:

```json
{
  "summary":      {"...": "decision-relevant state: IDs, status, headline quantities"},
  "evidence":     {"...": "detail supporting the summary: diagnostics, intervals, plans"},
  "warnings":     ["...server-raised caveats; each has a code and message"],
  "provenance":   {"...": "fingerprints, parent model IDs, library versions"},
  "next_actions": ["...server hints for the natural next call"]
}
```

A failed call returns `{"error": {"code", "message", "retryable", "user_actionable", "suggested_action", "evidence"}}`. Some fields are optional.

Rules:

- Read `summary` first. Branch on its status fields (`decision_status`, `valid_for_modeling`, `mmm_candidate`, job `status`), never on your impression of the numbers.
- Every entry in `warnings` must reach the user in plain language. You may group them; you may not drop them.
- `next_actions` are hints. Your skill's gates still apply: a hint that names `optimize_budget` does not authorize it on an undiagnosed model.
- Quote numbers from the envelope exactly, with their interval or distribution summary. When a number you need is absent, say it is absent.

## 3. The ID ledger

Keep a running ledger in your working notes and restate it when you hand off between skills:

| Key | Comes from | Used by |
| --- | --- | --- |
| `dataset_id` | `register_dataset` / `list_datasets` | inspect, validate, fit, CLV fits |
| `transformed_dataset_id` | `transform_ad_export` | inspect, validate, fit (use it in place of the raw export) |
| `model_id` (MMM) | `fit_mmm` / fit job result | diagnose, evidence, decisions |
| calibrated child `model_id` | `calibrate_mmm` | must be re-diagnosed on its own |
| `decision_status` per model | `diagnose_mmm` | gate for iROAS and budget tools |
| `job_id` + `idempotency_key` | `submit_*_job` | status, poll, recover, resume, cancel |
| `purchase_model_id` / `value_model_id` | `fit_purchase_model` / `fit_value_model` | CLV predictions |

Never invent an ID, never shorten one, and never swap a parent model ID for its calibrated child or a purchase model ID for a value model ID.

## 4. Synchronous call or background job

MCMC sampling usually takes minutes, and remote HTTP clients often drop long requests. Choose the job form whenever the call samples a posterior or runs an optimizer over many cells:

| Work | Synchronous tool | Background job tool | Prefer the job when |
| --- | --- | --- | --- |
| Fit an MMM | `fit_mmm` | `submit_fit_mmm_job` | almost always on a remote connection |
| Reshape an ad-platform export | `transform_ad_export` | `submit_transform_ad_export_job` | the export is large or multi-market |
| Static budget allocation | `optimize_budget` | `submit_budget_optimization_job` | panel (geo) models or long horizons |
| Weekly flighting | `optimize_flighting` | `submit_flighting_optimization_job` | more than a few channels or weeks |
| Time-slice cross-validation | `cross_validate_mmm` | `submit_cross_validate_mmm_job` | always; it refits per fold |
| Prior sensitivity | `evaluate_prior_sensitivity` | `submit_prior_sensitivity_job` | always; it refits per variant |

`inspect_dataset`, `validate_dataset`, `diagnose_mmm`, `get_model_status`, contributions, iROAS, and CLV predictions are quick and stay synchronous.

Give every job a deterministic `idempotency_key` built from the work it represents, for example `"<dataset_id>:fit:<first 12 hex chars of SHA-256 of the canonical config JSON>"`. If you are cut off and submit again with the same key, the server returns the existing job instead of paying for the same sampling twice. The server matches on the key alone, so the key must change whenever any input changes; deriving it from a hash of the full config does that automatically; reusing a key for different work silently returns the old job.

## 5. Polling budget

- `poll_job_progress(job_id, timeout_seconds=25)` waits server-side for up to `timeout_seconds` and returns the latest stage.
- Make at most **three consecutive polls** without visible progress. Then stop, tell the user the job ID and current stage, and continue in the next turn.
- A terminal status (`succeeded`, `failed`, `cancelled`) ends polling immediately.
- Never loop `get_job_status` rapidly; each poll is a tool call the user pays for in latency and tokens.

## 6. Error code playbook

| Code | What it means | Agent action |
| --- | --- | --- |
| `MODEL_NOT_DIAGNOSED` | Decision tool called before `diagnose_mmm` | Call `diagnose_mmm(model_id)`, then branch on `decision_status`. |
| `MODEL_NOT_VALIDATED` / `MODEL_REJECTED` | Gate blocked a decision tool | Stop the decision path. Explain the failed checks and route to `pymc-diagnostics-gate`. |
| `DATASET_FINGERPRINT_MISMATCH` | Dataset changed after the model was trained | Refit on the current dataset; the old model cannot drive decisions. |
| `INPUT_INVALID` / `INVALID_ARGUMENT` / `MISSING_INPUT` | Arguments failed the typed contract | Read `evidence`, fix the specific field, retry once. Do not guess new column names. |
| `MISSING_COLUMNS` / `DATASET_VALIDATION_FAILED` / `NON_RECTANGULAR_PANEL` / `MISSING_PERIODS` | Data cannot support the requested roles | Report the findings, propose the data fix, stop before fitting. |
| `CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE` | A client-local path was sent as `path` | Re-send the data as `content`, `content_base64`, or a public `url`. |
| `SSRF_DETECTED` / `UNSUPPORTED_SCHEME` / `REMOTE_DATASET_FETCH_FAILED` | URL rejected or unreachable | Ask the user for a public HTTPS URL or the file contents. |
| `DATASET_TOO_LARGE` / `REMOTE_DATASET_TOO_LARGE` / `RESOURCE_LIMIT_EXCEEDED` | Payload over server limits | Aggregate to weekly, drop unused columns, or split by market. |
| `INVALID_CONSTRAINT` / `DIMENSIONAL_CONSTRAINT_REQUIRED` | Budget constraint names an unknown channel, or a panel model got channel-level constraints | Use exact channel names from the model config; use `cell_constraints` for panel models. |
| `OPTIMIZATION_INFEASIBLE` / `OPTIMIZATION_FAILED` | Constraints cannot be met or the optimizer did not converge | Show the conflicting floors, caps, and budget. Ask the user which one to change. Never relax them yourself. |
| `INVALID_FINANCIAL_ASSUMPTIONS` | Margin or revenue inputs are inconsistent | Ask the user for the missing or corrected business inputs. |
| `CLV_LINEAGE_MISMATCH` / `INVALID_CLV_MODEL_TYPE` / `MISSING_RFM_COLUMNS` | Wrong model family or RFM columns | Match purchase and value models fitted on the same customers; map RFM columns explicitly. |
| `JOB_NOT_FOUND` | Unknown or foreign job ID | Call `list_jobs`; do not resubmit on a guess. |
| `JOB_NOT_RESUMABLE` / `INVALID_JOB_STATE` | Resume requested from a state that cannot resume | Call `recover_execution_state` and follow its flags. |
| `OPERATION_CANCELLED` / `JOB_CANCELLED` | Work was cancelled | Report it. Resubmit only if the user asks. |
| `PLOT_NOT_CACHED` | Plot resource read before generation | Call `get_posterior_plots` first. |
| `AUTH_REQUIRED` / `AUTH_FORBIDDEN` / `DATASET_ACCESS_DENIED` | Missing credentials or another tenant's object | Tell the user; never retry with a different ID to get around it. |
| `SAMPLING_DIVERGED` / `POOR_CHAIN_CONVERGENCE` / `INSUFFICIENT_EFFECTIVE_SAMPLE_SIZE` / `NUMERICAL_INSTABILITY` | Sampler health failure | Route to `pymc-diagnostics-gate` remediation. |
| `UPSTREAM_TIMEOUT` / `UPSTREAM_UNAVAILABLE` and any error with `retryable: true` | Transient infrastructure problem | Retry once. If it repeats, report it with the `error_id`. |

For any code not listed, show `message` and `suggested_action` to the user and stop at the last supported claim.

## 7. Hard limits

- Model-dependent numbers (contributions, iROAS, response, allocations, CLV, diagnostics) come from tool output only. No mental math, no Python you write yourself, no estimates from charts.
- A rejected or undiagnosed model never drives a budget, iROAS, or flighting answer, however the user phrases the request.
- Constraints the user gives are kept exactly. If they conflict, say so and ask.
- Deprecated tools (`fit_clv_model`, `predict_customer_clv`) are not used for new work.
- Administrative tools (`archive_model`, `cleanup_server_storage`) run only on an explicit user request.

## 8. Shape of the final answer

Use the [scientific answer contract](marketing://skills/references/scientific-answer-contract) for analytical results and the [marketing decision playbook](marketing://skills/references/marketing-decision-playbook) to phrase them for a marketing audience. Operational replies (job running, dataset registered) can be two or three sentences with the relevant IDs.
