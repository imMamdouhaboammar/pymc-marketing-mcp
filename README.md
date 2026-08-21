# PyMC Marketing MCP

LLMs can explain marketing data. They should not invent marketing science.

PyMC Marketing MCP gives MCP-compatible agents a controlled interface to Bayesian Marketing Mix Modeling with PyMC-Marketing. It handles dataset checks, MMM fitting, diagnostic gating, posterior contribution analysis, total and marginal iROAS, counterfactual spend scenarios, and constrained budget allocation while keeping the statistical computation inside PyMC-Marketing.

The core boundary is simple: the agent frames the business question and explains evidence. PyMC-Marketing computes the statistical quantities. The MCP layer validates inputs, persists artifacts, applies decision gates, reports uncertainty, and records provenance.

```text
User question
  -> AI agent
  -> MCP tool
  -> dataset / model validation
  -> PyMC-Marketing
  -> posterior evidence
  -> decision gate
  -> structured result + uncertainty + provenance
  -> AI explanation
```

## Decision Integrity release

Version `0.2.0` hardens the parts that directly affect spend decisions:

- `get_incremental_roas` uses PyMC-Marketing's incrementality interface for both total iROAS and marginal iROAS.
- `simulate_budget` evaluates the exact requested allocation with posterior response sampling. It does not disguise a fixed scenario as an optimization problem.
- `optimize_budget` compares a historical-share baseline with the recommended allocation using posterior response distributions.
- `diagnose_mmm` checks sampler health plus posterior predictive coverage, predictive error, and residual autocorrelation.
- Multidimensional datasets use `date + dims` as the observation key and must form a rectangular panel.
- Budget simulations and constraints can address exact cells such as `Meta x Riyadh` through `cell_changes` and `cell_constraints`.

See `docs/DECISION-INTEGRITY.md` for the contracts and safety policy.

## Current compatibility

- Python 3.11 to 3.13
- PyMC-Marketing `>=0.19.4,<0.20`
- PyMC-Marketing 0.19.x multidimensional MMM and budget wrapper APIs
- Official MCP Python SDK v2
- CSV and Parquet datasets
- SQLite metadata and NetCDF model artifacts for local deployment

## Install

```bash
uv sync --extra dev
uv run pytest
```

## Run with stdio

```bash
uv run marketing-mcp --transport stdio
```

## Run with Streamable HTTP

```bash
uv run marketing-mcp --transport streamable-http --host 127.0.0.1 --port 8000
# endpoint: http://127.0.0.1:8000/mcp
```

For a public hostname, configure the current MCP SDK transport-security host/origin allowlist instead of relying on localhost defaults.

## Docker

```bash
docker compose up --build
```

## Core flow

1. `register_dataset`
2. `inspect_dataset`
3. `validate_dataset`
4. `fit_mmm`
5. `diagnose_mmm`
6. `get_channel_contributions`
7. `get_incremental_roas`
8. `get_response_curves`
9. `simulate_budget`
10. `optimize_budget`
11. Explain the posterior result, diagnostics, assumptions, and provenance

## iROAS output

`get_incremental_roas` reports two different questions instead of collapsing them into one number:

```json
{
  "channel": "meta",
  "total_iroas": {
    "median": 3.4,
    "lower": 2.1,
    "upper": 4.8,
    "interval_probability": 0.94,
    "probability_gt_1": 0.97
  },
  "marginal_iroas": {
    "median": 1.6,
    "lower": 0.7,
    "upper": 2.5,
    "interval_probability": 0.94,
    "probability_gt_1": 0.78
  }
}
```

Total iROAS describes historical incremental contribution per unit of spend. Marginal iROAS describes the estimated return from additional spend around the current operating point.

## Scenario output

A request such as Meta -20% and Google +15% is evaluated as that exact allocation. The tool returns separate posterior summaries for the baseline and scenario plus a paired comparison:

```json
{
  "baseline_response": {
    "median": 7100000,
    "lower": 6600000,
    "upper": 7600000,
    "interval_probability": 0.94
  },
  "scenario_response": {
    "median": 7440000,
    "lower": 6860000,
    "upper": 8010000,
    "interval_probability": 0.94
  },
  "comparison": {
    "median": 340000,
    "lower": -80000,
    "upper": 710000,
    "interval_probability": 0.94,
    "probability_scenario_beats_baseline": 0.87,
    "expected_change_pct": 4.8
  }
}
```

The example above describes the response schema only. It is not a claimed model result.

## Multidimensional budgets

For a model fitted with `dims=["geo"]`, channel-wide changes remain supported and exact cells can be targeted:

```json
{
  "model_id": "mmm_abc123",
  "planning_periods": 8,
  "changes": {},
  "cell_changes": [
    {
      "channel": "meta",
      "dimensions": {"geo": "riyadh"},
      "type": "relative",
      "value": -0.20
    },
    {
      "channel": "google",
      "dimensions": {"geo": "jeddah"},
      "type": "relative",
      "value": 0.15
    }
  ]
}
```

Optimization can constrain exact cells:

```json
{
  "model_id": "mmm_abc123",
  "budget": 4000000,
  "planning_periods": 8,
  "cell_constraints": [
    {
      "channel": "meta",
      "dimensions": {"geo": "riyadh"},
      "min": 400000,
      "max": 1000000
    }
  ]
}
```

For multidimensional models, legacy channel-level `min/max/fixed` constraints are rejected because their meaning is ambiguous across dimension cells. Use `cell_constraints` instead.

## Diagnostic gate

A successful sampler run does not automatically enable budget decisions.

```text
Dataset validation
  -> fit
  -> sampler diagnostics
  -> posterior predictive diagnostics
  -> decision status
  -> decision tools
```

Decision tools are blocked when hard failures are present. Warnings produce `approved_with_caution` rather than a fabricated single accuracy score.

## Tool safety

There is no `eval`, `exec`, `run_python`, shell tool, arbitrary SQL tool, pickle loader, or caller-selected model artifact path. Decision tools operate on registered model IDs. If diagnostics reject a model, budget tools return `MODEL_NOT_VALIDATED`.

## Synthetic demo

The repository includes a deterministic weekly data generator with Meta, Google, TikTok, YouTube, discount, seasonality, adstock, saturation, and noise. With dependencies installed:

```bash
uv run marketing-mcp-demo --fast
```

`--fast` is a smoke run, not a production sampling configuration.

## Generic MCP client

Point an MCP v2 client at the Streamable HTTP endpoint:

```text
http://127.0.0.1:8000/mcp
```

For stdio clients, configure `uv run marketing-mcp --transport stdio` as the MCP server command. Client configuration keys differ across products, so verify the target client's current documentation rather than copying stale vendor-specific JSON.

## Repository map

```text
src/marketing_mcp/
  mcp/            protocol tools + resources
  services/       application workflows
  domain/         validation, diagnostics, allocation contracts
  adapters/       PyMC-Marketing boundary
  storage/        metadata + artifacts
  schemas/        typed contracts
tests/             unit + integration + statistical hooks
docs/              architecture, contracts, safety, security
```

## Known limitations

- The runtime used to assemble and unit-test this repository does not contain `pymc-marketing` or `mcp`, and outbound package installation is unavailable. Real NUTS sampling, MCP client invocation, Streamable HTTP, and the Docker dependency build therefore remain deployment-time verification items.
- The predictive gate currently uses in-sample posterior predictive coverage, normalized RMSE, and residual autocorrelation. Time-slice cross-validation, prior sensitivity, and calibration with experiments are not yet hard decision gates.
- MCP v2 Tasks are not claimed as implemented until the installed SDK task interface is exercised end to end. Model lifecycle persistence is present without inventing a custom polling protocol.
- The current deployment is single-tenant. Storage interfaces are separated so tenant-aware metadata and object stores can be added later.
