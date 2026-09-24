---
name: pymc-dataset-readiness
version: 2.0.0
description: Use when marketing data must be uploaded, registered, reshaped from an ad-platform export, inspected, role-checked, or validated before MMM fitting.
---
# PyMC Dataset Readiness

Gets marketing data onto the server and proves it can support an MMM before any sampling starts. The server does ingestion and validation; the agent chooses roles and explains findings.

## Entry checks

- Call `list_datasets` first. If a registered dataset already matches the user's file (same rows, same period), reuse its `dataset_id`.
- Ask the user which column is the business outcome when it is not obvious. Revenue or orders from Shopify or the CRM are good targets; ad-platform attributed conversions are poor ones (see the [marketing decision playbook](marketing://skills/references/marketing-decision-playbook)).

## Step 1: get the data onto the server

`register_dataset` accepts exactly one source:

```json
{"content": "date,revenue,meta_spend,google_spend\n2024-01-01,...", "filename": "weekly_mmm.csv"}
{"content_base64": "<base64 bytes>", "filename": "weekly_mmm.parquet"}
{"url": "https://example.com/exports/weekly_mmm.csv"}
```

- On a remote connection, send the file itself as `content` (CSV text) or `content_base64` (binary, gzip, parquet), or a public HTTPS `url`.
- `path` means a file **on the server** inside its ingest directory. A path from the user's laptop or your sandbox (`/Users/...`, `/mnt/data/...`, `C:\...`) fails with `CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE`. Re-send the contents instead.
- Keep the returned `dataset_id` and `fingerprint` in the ID ledger.

## Step 2 (only for raw ad-platform exports): reshape long to wide

Exports from Meta, Google Ads, TikTok, or LinkedIn usually arrive long: one row per date and campaign or platform. Pivot them with `transform_ad_export` (or `submit_transform_ad_export_job` for large files):

```json
{
  "dataset_id": "<raw export dataset_id>",
  "date_column": "date",
  "channel_column": "platform",
  "spend_column": "spend",
  "target_columns": ["purchases", "revenue"],
  "dimension_columns": ["country"],
  "frequency": "D"
}
```

- `frequency` must match the grain the export already has: `"D"` for daily rows, a pandas weekly anchor such as `"W-MON"` when every row is dated on a Monday. It fills calendar gaps; it does **not** aggregate daily rows into weeks. A weekly frequency on daily data drops rows.
- Read `summary.spend_reconciled` and `summary.spend_delta`. If spend did not reconcile, stop and show the delta; the reshaped file lost or duplicated spend.
- `summary.inserted_periods` counts dates the server added. Spend in those rows is set to 0 (correct: no delivery) and targets are also set to 0, which is wrong if the gap is a tracking outage. Ask the user when inserted periods are more than a handful.
- New channel columns are named `<channel>_spend`. Continue with `summary.transformed_dataset_id` in every later step.

## Step 3: inspect

`inspect_dataset(dataset_id)` returns `possible_targets`, `possible_channels`, `possible_controls`, `frequency`, `date_range`, `missing_periods`, `detected_dimensions`, `is_long_form`, `mmm_candidate`, and `clarification_requests`.

- `is_long_form: true` means Step 2 is needed before validation.
- Answer every entry in `clarification_requests` with the user, then pass the answers as `user_overrides`, for example `{"target_column": "revenue", "channels": ["meta_spend", "google_spend"], "controls": ["promo_flag"], "dims": ["geo"]}`.
- Candidate lists are suggestions. A column named `tv_grps` or `influencer_posts` may be media; `price` or `discount_pct` is a control, never a channel.

## Step 4: validate with explicit roles

```json
{
  "dataset_id": "<dataset_id>",
  "date_column": "date",
  "target_column": "revenue",
  "channel_columns": ["meta_spend", "google_spend", "tiktok_spend", "tv_spend"],
  "control_columns": ["promo_flag", "ramadan_week", "avg_price"],
  "dims": ["geo"]
}
```

Branch on `summary.valid_for_modeling`:

- `true`: record the validated role mapping and hand it to `pymc-mmm-workflow` unchanged.
- `false`: stop. Present each blocking finding with its suggested fix. Never fit on an invalid dataset.

## What the findings mean in marketing terms

| Finding code | Plain meaning | What to tell the user |
| --- | --- | --- |
| `INSUFFICIENT_DATA` / `LIMITED_HISTORY` | Under 52 periods is blocking; under 104 is a caution (current server policy) | Add history, or accept wide intervals and treat results as directional |
| `MISSING_PERIODS` / `DUPLICATE_PERIOD` / `INVALID_DATE` | The calendar has holes or repeats | Fix the export; decide whether gaps mean zero spend or missing tracking |
| `NON_RECTANGULAR_PANEL` / `MISSING_DIMENSION_VALUE` / `EMPTY_DIMENSION` | Some markets lack some weeks | Fill missing market-weeks or drop the incomplete market |
| `NEGATIVE_MEDIA` / `NON_NUMERIC_MEDIA` | Spend column contains refunds, text, or currency symbols | Clean the column; spend must be numeric and non-negative |
| `NO_SPEND_VARIATION` | A channel spent the same every period | Its effect cannot be separated from the baseline; drop it or merge it |
| `HIGH_CHANNEL_CORRELATION` | Two channels always moved together | Merge them or expect wide, unstable attribution between them |
| `LONG_ZERO_SPEND_RUN` / `STAGGERED_CHANNEL_LIFECYCLES` | A channel was off for long stretches or launched mid-period | Results for it rest on few active weeks; say so in any recommendation |
| `EXTREME_OUTLIERS` | Spikes in spend or target | Check for data errors or one-off events; add an event control |
| `BAD_TARGET` / `POSSIBLE_TARGET_TRACKING_GAP` | The KPI has flat stretches, zeros, or tracking breaks | Confirm with the user before modeling |
| `MIXED_CAMPAIGN_OBJECTIVES` | Awareness and conversion campaigns are summed together | Split channel columns by objective when they were run independently |
| `UNMODELED_MARKET_HETEROGENEITY` | Markets behave differently but were summed | Use a panel with `dims=["geo"]` |

Validation proves structural readiness. It does not prove identifiability, convergence, predictive accuracy, or causality. Carry every warning forward into the modeling and decision answers.

## Stop conditions

- The user cannot provide the data in a form the remote server can read.
- `spend_reconciled` is false after a transform.
- `valid_for_modeling` is false.
- Roles are ambiguous and the user has not confirmed them.

## Handoff

Pass `dataset_id` (or `transformed_dataset_id`), the confirmed role mapping, and every validation warning to `pymc-mmm-workflow`.
