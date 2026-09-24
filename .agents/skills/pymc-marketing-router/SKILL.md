---
name: pymc-marketing-router
version: 2.0.0
description: Use when the user intent spans PyMC Marketing MCP workflows, the session is just starting, or the correct specialist skill is not yet clear.
---
# PyMC Marketing Router

Entry point for any agent connected to this server. It decides which specialist skill runs first and in what order the rest follow. It never computes model-dependent numbers.

## First contact with the server

1. Call `get_skill_guidance(task="<the user's request, verbatim>")`. The result names the routed skill and inlines its full guidance, so you can start working immediately.
2. Read the [agent operating protocol](marketing://skills/references/agent-operating-protocol) once per session. It covers the result envelope, the ID ledger, background jobs, polling limits, and the error-code playbook. If your host cannot read resources, call `get_skill_guidance(reference_name="agent-operating-protocol")`.
3. Before creating new objects, check what the server already holds: `list_datasets`, `list_jobs(limit=10)`, and `get_model_status(model_id)` for any model the user names.

## Route by intent

| The user wants to | Load | Typical first call |
| --- | --- | --- |
| upload, register, inspect, or check marketing data; reshape an ad-platform export | `pymc-dataset-readiness` | `list_datasets` or `register_dataset` |
| fit a media mix model, or continue the MMM lifecycle | `pymc-mmm-workflow` | `validate_dataset` |
| understand divergences, R-hat, ESS, rejection, or decision status | `pymc-diagnostics-gate` | `diagnose_mmm` |
| cross-validate, test prior sensitivity, compare or pick among models | `pymc-model-validation` | `get_model_status` for each model |
| know which channels drive results: contribution, iROAS, response curves, saturation | `pymc-incrementality-evidence` | `get_channel_contributions` |
| simulate a spend change, reallocate a fixed budget, or plan weekly flighting | `pymc-budget-optimization` | `get_model_status` |
| feed a lift test or geo experiment into the model | `pymc-lift-calibration` | `get_model_status` |
| predict purchases, churn, P(alive), spend per order, or CLV | `pymc-clv-customer-analytics` | `list_datasets` |
| handle a long fit, timeout, disconnect, progress, resume, or cancel | `pymc-job-resilience` | `list_jobs` |
| get posterior plots or download a model or dataset artifact | `pymc-artifact-delivery` | `get_posterior_plots` |

## Multi-intent requests

Run skills in dependency order and pass the ID ledger from one to the next:

```text
dataset-readiness -> mmm-workflow -> diagnostics-gate -> (model-validation) -> incrementality-evidence -> budget-optimization
                                                    \-> lift-calibration -> diagnostics-gate on the child model
clv-customer-analytics runs on its own RFM dataset and never needs the MMM gate.
```

- "Meta looks strong, move 40% of TV into it" is a budget request that depends on an approved model. Establish the model and its diagnosis before any simulation.
- "Which channel caused the sales lift?" routes to evidence interpretation. MMM evidence is observational; say so and offer calibration.
- "Is my data good enough and what would the model say?" starts with readiness and stops if validation fails.

## Marketing framing

Most requests arrive as business questions. Map them with the [marketing decision playbook](marketing://skills/references/marketing-decision-playbook) before choosing tools. It covers the question-to-tool table, the ROAS vocabulary (platform ROAS, total and marginal iROAS, lift), break-even logic, MENA calendar effects, and how to phrase recommendations for a marketing lead.

## Routing discipline

- Prefer one specialist skill at a time. Load the next only after the current one's gate passes.
- If routing is uncertain, `get_skill_guidance` returns alternatives with scores. Pick the top one and mention the runner-up only if the user's wording is genuinely ambiguous.
- `list_agentic_skills` returns the compact catalog; `get_skill_workflow_map` returns prerequisites, gates, and continuations for every skill.
- Never invent a workflow, tool, or argument name. When the catalog has nothing that fits, say what the server can do instead.
- Read the [scientific answer contract](marketing://skills/references/scientific-answer-contract) before writing any analytical conclusion.
