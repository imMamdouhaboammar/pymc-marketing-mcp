---
name: pymc-dataset-readiness
version: 1.0.0
description: Use when marketing data must be registered, inspected, role-checked, or validated before MMM fitting.
---

# PyMC Dataset Readiness

Use the server as the authority for ingestion and validation. Do not reproduce dataset validation in prompt arithmetic.

## Safe ingestion

For a remote client, prefer `register_dataset` with uploaded/raw `content`, `content_base64`, or a server-supported URL. A `path` refers to the **server filesystem** and must already be inside the configured ingest boundary. Never send `/Users/alice/Desktop/data.csv` or another client-local path and assume the remote server can read it.

## Workflow

1. `list_datasets` when an existing server dataset may already exist.
2. `register_dataset` only when new content must be ingested.
3. `inspect_dataset` to discover columns, frequency hints, target/channel/control candidates, missing periods, and MMM-candidate status.
4. `validate_dataset` with the intended date, target, channels, controls, and panel dimensions.
5. Stop on validation errors. Continue to `pymc-mmm-workflow` only with a valid dataset and explicit role mapping.

## What current validation checks

The repository currently checks required columns, parseable/unique date keys, rectangular panel grids, missing values, numeric and non-negative media, channel variation, target variation, temporal gaps, and warnings such as long zero-spend runs, strong channel correlation, and extreme outliers. The current implementation treats fewer than 52 unique periods as an error and less than 104 as limited-history caution. These are **server policy**, not universal Bayesian laws.

Validation establishes structural readiness; it does not prove identifiability, convergence, predictive adequacy, causal identification, or commercial usefulness. Preserve all findings and suggested actions in downstream work.
