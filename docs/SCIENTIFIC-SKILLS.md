# Scientific Skill System

<!-- GENERATED FILE - do not edit by hand. -->

The canonical Agent Skill packages live under `.agents/skills/`. The MCP delivery layer
packages the same validated content so remote clients can discover guidance lazily without
a repository checkout. Agent Skills complement MCP schemas; they do not execute statistics.

```text
                 PyMC Marketing MCP
                        |
        +---------------+----------------+
        |                                |
 MCP Execution Surface             Skill Knowledge Surface
 Tools / Resources                 Catalog / Skill Resources
                                  Manifests / Maps / Router Tool
        |                                |
        +---------------+----------------+
                        |
                  AI Client / Host
                        |
                   User Question
```

## Discovery contract

- `marketing://skills` is a compact deterministic catalog; it does not inline every skill.
- `marketing://skills/{skill_name}` returns one canonical `SKILL.md` lazily.
- `marketing://skills/{skill_name}/manifest` returns typed machine-readable routing metadata.
- Tool/workflow/decision-gate maps are derived from the same manifests and capability registry.
- `get_skill_guidance` is the model-callable fallback for hosts that do not surface resources to the model.
- No non-standard `skills/list` protocol method is introduced.
- MCP prompts are intentionally not added: the routing tool plus lazy resources is the smaller cross-host surface; prompts are user-selected in many clients and would duplicate workflow text.

Clients should discover the catalog, select one skill, fetch only that skill, and load deeper references only when needed. Runtime Skill assets are bundled once at build time and cached in an immutable process registry.

The installed MCP SDK v2 supports cache hints. The server applies private five-minute hints to discovery lists (`tools/list`, `resources/list`, and `resources/templates/list`) while leaving `resources/read` uncached globally so model/dataset resource semantics are unchanged. The Skill catalog is deterministically ordered and publishes stable catalog/content hashes for client-side reuse across reconnects.

## Current-state capability / Skill matrix

| Capability | MCP primitive | Status | Decision-gated | Existing skill / role | Gap |
| --- | --- | --- | --- | --- | --- |
| `marketing://clv/{model_id}` | resource | experimental | no | resource: pymc-clv-customer-analytics | none |
| `marketing://datasets/{dataset_id}` | resource | experimental | no | resource: pymc-dataset-readiness, pymc-mmm-workflow | none |
| `marketing://models/{model_id}` | resource | experimental | no | resource: pymc-artifact-delivery, pymc-budget-optimization, pymc-diagnostics-gate, pymc-incrementality-evidence, pymc-lift-calibration, pymc-mmm-workflow, pymc-model-validation | none |
| `marketing://models/{model_id}/diagnostics` | resource | experimental | no | resource: pymc-budget-optimization, pymc-diagnostics-gate, pymc-incrementality-evidence, pymc-lift-calibration, pymc-model-validation | none |
| `marketing://models/{model_id}/lineage` | resource | experimental | no | resource: pymc-lift-calibration, pymc-model-validation | none |
| `marketing://models/{model_id}/plots/{plot_type}` | resource | experimental | no | resource: pymc-artifact-delivery | none |
| `marketing://skills` | resource | experimental | no | resource: pymc-marketing-router | none |
| `marketing://skills/decision-gates` | resource | experimental | no | skill-delivery infrastructure | none |
| `marketing://skills/references/scientific-answer-contract` | resource | experimental | no | skill-delivery infrastructure | none |
| `marketing://skills/references/scientific-source-ledger` | resource | experimental | no | skill-delivery infrastructure | none |
| `marketing://skills/tool-map` | resource | experimental | no | skill-delivery infrastructure | none |
| `marketing://skills/workflow-map` | resource | experimental | no | skill-delivery infrastructure | none |
| `marketing://skills/{skill_name}` | resource | experimental | no | skill-delivery infrastructure | none |
| `marketing://skills/{skill_name}/manifest` | resource | experimental | no | skill-delivery infrastructure | none |
| `archive_model` | tool | experimental | no | administrative: pymc-model-validation | none |
| `calibrate_mmm` | tool | stable | no | primary: pymc-lift-calibration | none |
| `cancel_job` | tool | stable | no | primary: pymc-job-resilience | none |
| `cleanup_server_storage` | tool | experimental | no | administrative: pymc-artifact-delivery | none |
| `compare_models` | tool | stable | no | primary: pymc-model-validation | none |
| `cross_validate_mmm` | tool | stable | no | primary: pymc-model-validation | none |
| `diagnose_mmm` | tool | stable | no | primary: pymc-diagnostics-gate | none |
| `estimate_customer_lifetime_value` | tool | stable | no | primary: pymc-clv-customer-analytics | none |
| `evaluate_prior_sensitivity` | tool | stable | no | primary: pymc-model-validation | none |
| `export_artifact_to_sandbox` | tool | experimental | no | primary: pymc-artifact-delivery | none |
| `fit_clv_model` | tool | deprecated | no | deprecated: pymc-clv-customer-analytics | none |
| `fit_mmm` | tool | stable | no | primary: pymc-mmm-workflow | none |
| `fit_purchase_model` | tool | stable | no | primary: pymc-clv-customer-analytics | none |
| `fit_value_model` | tool | stable | no | primary: pymc-clv-customer-analytics | none |
| `get_agent_insights` | tool | stable | no | secondary: pymc-diagnostics-gate | none |
| `get_channel_contributions` | tool | stable | no | primary: pymc-incrementality-evidence | none |
| `get_churn_risk_cohorts` | tool | experimental | no | primary: pymc-clv-customer-analytics | none |
| `get_incremental_roas` | tool | stable | no | primary: pymc-incrementality-evidence | none |
| `get_job_status` | tool | stable | no | primary: pymc-job-resilience | none |
| `get_model_status` | tool | stable | no | secondary: pymc-artifact-delivery, pymc-budget-optimization, pymc-diagnostics-gate, pymc-incrementality-evidence, pymc-job-resilience, pymc-lift-calibration, pymc-mmm-workflow, pymc-model-validation | none |
| `get_posterior_plots` | tool | experimental | no | primary: pymc-artifact-delivery | none |
| `get_response_curves` | tool | experimental | no | primary: pymc-incrementality-evidence | none |
| `get_skill_guidance` | tool | experimental | no | primary: pymc-marketing-router | none |
| `get_skill_workflow_map` | tool | experimental | no | secondary: pymc-marketing-router | none |
| `inspect_dataset` | tool | stable | no | primary: pymc-dataset-readiness | none |
| `list_agentic_skills` | tool | experimental | no | secondary: pymc-marketing-router | none |
| `list_datasets` | tool | stable | no | primary: pymc-dataset-readiness | none |
| `list_jobs` | tool | stable | no | primary: pymc-job-resilience | none |
| `optimize_budget` | tool | stable | yes | primary: pymc-budget-optimization | none |
| `optimize_flighting` | tool | stable | yes | primary: pymc-budget-optimization | none |
| `poll_job_progress` | tool | experimental | no | primary: pymc-job-resilience | none |
| `predict_customer_clv` | tool | deprecated | no | deprecated: pymc-clv-customer-analytics | none |
| `predict_expected_purchases` | tool | stable | no | primary: pymc-clv-customer-analytics | none |
| `predict_expected_spend` | tool | stable | no | primary: pymc-clv-customer-analytics | none |
| `predict_probability_alive` | tool | stable | no | primary: pymc-clv-customer-analytics | none |
| `recommend_next_measurement` | tool | experimental | no | primary: pymc-incrementality-evidence | none |
| `record_agent_insight` | tool | stable | no | secondary: pymc-diagnostics-gate | none |
| `recover_execution_state` | tool | experimental | no | primary: pymc-job-resilience | none |
| `register_dataset` | tool | stable | no | primary: pymc-dataset-readiness | none |
| `resume_job` | tool | experimental | no | primary: pymc-job-resilience | none |
| `select_best_model` | tool | experimental | no | primary: pymc-model-validation | none |
| `simulate_budget` | tool | stable | yes | primary: pymc-budget-optimization | none |
| `submit_budget_optimization_job` | tool | stable | no | primary: pymc-job-resilience | none |
| `submit_cross_validate_mmm_job` | tool | stable | no | primary: pymc-job-resilience | none |
| `submit_fit_mmm_job` | tool | stable | no | primary: pymc-job-resilience | none |
| `submit_flighting_optimization_job` | tool | stable | no | primary: pymc-job-resilience | none |
| `submit_prior_sensitivity_job` | tool | stable | no | primary: pymc-job-resilience | none |
| `submit_transform_ad_export_job` | tool | stable | no | primary: pymc-job-resilience | none |
| `transform_ad_export` | tool | stable | no | primary: pymc-dataset-readiness | none |
| `validate_dataset` | tool | stable | no | primary: pymc-dataset-readiness | none |

## Authority and safety

Local source/tests define server policy; PyMC-Marketing, PyMC, and ArviZ define library semantics only where the server delegates to them. Model-dependent quantities must come from those executed/persisted outputs. Diagnostic approval is not causal proof, rejected decision gates cannot be bypassed with prompt arithmetic, uncertainty and caution states remain visible, and deprecated CLV wrappers are compatibility-only.

See `.agents/references/scientific-source-ledger.md` and `.agents/references/scientific-answer-contract.md` for provenance and analytical communication rules.
