# Tool Contracts

Every MCP tool returns structured, agent-oriented data. Stable errors explain what failed, evidence where available, and a next action. Large posterior arrays stay server-side.

## Dataset

### `register_dataset(path)`
Returns a stable dataset ID, format, row count, and SHA-256 fingerprint.

### `inspect_dataset(dataset_id)`
Returns row count, inferred frequency, date range, candidate target/channel/control columns, missing periods, and inspection findings.

### `validate_dataset(...)`
Runs MMM-specific validation. When `dims` are present, observation uniqueness is evaluated on `date + dims`, and the panel must contain the same dates for every dimension combination.

## Modeling

### `fit_mmm(config)`
Fits a PyMC-Marketing MMM from a controlled typed configuration. Arbitrary Python is not accepted.

### `get_model_status(model_id)`
Returns persisted lifecycle state and safe failure information.

### `diagnose_mmm(model_id)`
Returns:

- divergences
- maximum R-hat
- minimum bulk ESS
- posterior predictive target
- 94% posterior predictive coverage when available
- posterior predictive RMSE and normalized RMSE
- lag-1 residual autocorrelation when a date dimension is available
- `approved | approved_with_caution | rejected`

## Analysis

### `get_channel_contributions(model_id)`
Returns posterior contribution summaries from the fitted model artifact.

### `get_incremental_roas(model_id)`
Returns total and marginal iROAS from PyMC-Marketing incrementality calculations. Each summary contains mean, median, 94% interval, and probability of exceeding 1.

### `get_response_curves(model_id)`
Returns compact response/saturation summaries from the supported PyMC-Marketing response-curve API.

## Decisions

### `simulate_budget(config)`
Requires a diagnosed model that passed the decision gate. It evaluates the requested allocation directly through posterior response sampling.

Single-dimensional input can use:

```json
{
  "changes": {
    "meta": {"type": "relative", "value": -0.20}
  }
}
```

Multidimensional input can use:

```json
{
  "cell_changes": [
    {
      "channel": "meta",
      "dimensions": {"geo": "riyadh"},
      "type": "relative",
      "value": -0.20
    }
  ]
}
```

Output includes baseline allocation, scenario allocation, baseline posterior response, scenario posterior response, difference interval, and probability that the scenario beats baseline.

### `optimize_budget(config)`
Requires a diagnosed model that passed the decision gate. It uses PyMC-Marketing budget allocation and samples the response distribution for both the baseline and recommended allocation.

For a multidimensional model, exact cell bounds are supplied through `cell_constraints`:

```json
{
  "cell_constraints": [
    {
      "channel": "google",
      "dimensions": {"geo": "jeddah"},
      "min": 100000,
      "max": 600000
    }
  ]
}
```

Channel-only bounds remain supported for models without extra dimensions.

### `recommend_next_measurement(model_id)`
Returns evidence-gathering suggestions only when current validation or diagnostic signals support them. It can explicitly return that no single measurement is implied.

## Prohibited surfaces

No tool accepts Python source, shell commands, SQL, serialized Python objects, or caller-selected model artifact paths. Rejected models return `MODEL_NOT_VALIDATED` for budget decision calls.
