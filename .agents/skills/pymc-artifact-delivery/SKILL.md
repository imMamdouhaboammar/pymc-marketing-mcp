---
name: pymc-artifact-delivery
version: 2.0.0
description: Use when a user needs posterior plots, a stored model or dataset artifact, sandbox download delivery, or safe artifact lifecycle guidance.
---
# PyMC Artifact Delivery

Gets visual evidence and model files from the server to the user. Artifacts are server-owned: the agent requests them by model ID or server-issued URI, never by filesystem path, and never builds file bytes itself.

## Posterior plots

`get_posterior_plots` renders and caches plots for a fitted model:

```json
{"config": {"model_id": "<model_id>", "plot_types": ["channel_contribution_share", "saturation_curves"], "format": "png"}}
```

| `plot_types` value | Shows | Good for |
| --- | --- | --- |
| `channel_contribution_share` | Each channel's share of modeled outcome | "Which channels matter?" slides |
| `waterfall_decomposition` | Baseline, controls, and channels adding up to the outcome | Explaining what drives revenue overall |
| `saturation_curves` | Response vs spend per channel with uncertainty | Headroom and diminishing returns |
| `actual_vs_predicted` | Model fit against history | Building trust in the model, spotting missed events |

- Up to four types per call; `format` is `png` or `svg`.
- The result lists `generated` and `failed` types, with a `PLOT_FAILED` warning per failure. Report failures; do not describe a plot that was not generated.
- After generation, `marketing://models/{model_id}/plots/{plot_type}` returns the cached image. Reading it before generation returns `PLOT_NOT_CACHED`.
- Plots illustrate. Numbers in your answer still come from the typed tools (`get_channel_contributions`, `get_incremental_roas`, `get_response_curves`), never from reading values off an image.
- Plots of a rejected model get the label "model failed diagnostics; descriptive only".

## Model and dataset files

`export_artifact_to_sandbox` stages a downloadable copy (up to about 1 GB):

Export by model (MMM or CLV):

```json
{"model_id": "<mmm or clv model_id>", "export_name": "mmm_q3_v2"}
```

Or, as an alternative, export by a server-issued artifact URI:

```json
{"artifact_uri": "blob://<namespace>/<sha256>"}
```

Pass `model_id` for a model's posterior artifact (MMM or CLV), or an `artifact_uri` exactly as the server issued it. The result includes `download_url`, `sandbox_curl_command`, `python_snippet`, `sha256`, `size_bytes`, `filename`, and `retention_policy`.

- Give the user the download URL or curl command and the `sha256`, and tell them to verify the checksum after download.
- Exports are tracked for about 24 hours; downloads should happen within that window.
- If your host has a code sandbox, use the returned `python_snippet` to load the file there; otherwise hand the link to the user.
- The result's `next_actions` mentions `cleanup_server_storage`. Ignore that hint unless the user asked for cleanup.

## Administrative cleanup

`cleanup_server_storage(older_than_hours=24, dry_run=true)` lists what would be purged: scratch files, expired exports, orphan blobs. Run it only when an authorized user explicitly asks, show the dry-run report first, and run with `dry_run=false` only after they confirm.

## Stop conditions

Stop when the model or artifact does not exist (`MODEL_NOT_FOUND`, `ARTIFACT_NOT_FOUND`), when the caller is not authorized, or when the user supplies a local path or an arbitrary URL as an artifact location. Never guess a path or synthesize bytes.
