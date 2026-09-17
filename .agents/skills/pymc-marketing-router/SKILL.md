---
name: pymc-marketing-router
version: 1.0.0
description: Use when the user intent spans PyMC Marketing MCP workflows or the correct specialist skill is not yet clear.
---

# PyMC Marketing Router

Use this only for navigation. Do not turn it into a statistical encyclopedia and do not calculate model-dependent values here.

## Route by intent

| User intent | Load |
| --- | --- |
| inspect/register/validate marketing data | `pymc-dataset-readiness` |
| fit or continue the main MMM lifecycle | `pymc-mmm-workflow` |
| divergences, R-hat, ESS, rejection, decision status | `pymc-diagnostics-gate` |
| cross-validation, prior sensitivity, compare/select specifications | `pymc-model-validation` |
| contribution, iROAS, response curves, what the MMM supports | `pymc-incrementality-evidence` |
| simulate, allocate, or flight spend | `pymc-budget-optimization` |
| incorporate a lift experiment | `pymc-lift-calibration` |
| purchase frequency, P(alive), spend, CLV, churn | `pymc-clv-customer-analytics` |
| long-running fit, polling, disconnect, resume/cancel | `pymc-job-resilience` |
| posterior plot or artifact delivery | `pymc-artifact-delivery` |

## Routing discipline

Prefer one specialist skill. For multi-intent requests, load the first prerequisite skill and continue only after its gates pass. A request such as “Meta looks strong; move 40% of TV budget to it” is not an immediate optimizer call: establish the model, diagnostics state, then use the budget skill. “Which channel caused sales?” routes to evidence interpretation, not a claim of experimental causality.

If no route is confident, return the compact catalog or the top candidate plus alternatives; never invent a workflow or tool name. Read the shared [scientific answer contract](marketing://skills/references/scientific-answer-contract) only when producing analytical results.
