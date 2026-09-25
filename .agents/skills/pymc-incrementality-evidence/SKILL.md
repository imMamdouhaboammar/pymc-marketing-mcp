---
name: pymc-incrementality-evidence
version: 2.0.0
description: Use when a user asks about channel contribution, total or marginal iROAS, response curves, saturation, incrementality evidence, or what an MMM supports.
---
# PyMC Incrementality Evidence

Answers "which channels drive results, and how much more would extra spend bring?" with posterior evidence from the fitted model. Every number comes from these tools; the agent's job is to choose the right quantity, keep its uncertainty, and explain it in commercial terms.

## Entry checks

- A `model_id` confirmed with `get_model_status`.
- The model's current diagnosis. Contributions and response curves are descriptive and run on any fitted model; `get_incremental_roas` is decision-gated and needs `approved` or `approved_with_caution`. If the status is unknown, run `pymc-diagnostics-gate` first.

## Pick the quantity that answers the question

| User question | Quantity | Tool | Gated |
| --- | --- | --- | --- |
| "How much of our revenue came from each channel?" | Contribution | `get_channel_contributions(model_id)` | no |
| "What did each channel return per unit spent?" | Total iROAS | `get_incremental_roas(model_id)` | yes |
| "Where should the next unit of budget go?" | Marginal iROAS | `get_incremental_roas(model_id)` | yes |
| "Is channel X saturated? How much headroom is left?" | Response curve | `get_response_curves(model_id)` | no |
| "What should we test next?" | Measurement suggestions | `recommend_next_measurement(model_id)` (experimental) | no |

A good default sequence for "which channels are working": contributions, then iROAS, then response curves for the two or three channels the user cares about most.

## Reading the results

- **Contributions** return per channel `contribution_median` and a `credible_interval` (`lower`, `upper`, `probability: 0.94`). Report the range alongside the median. Channels whose intervals overlap heavily cannot be ranked with confidence.
- **iROAS** returns per channel `total_iroas` and `marginal_iroas` summaries computed by PyMC-Marketing's incrementality API over the whole fitted period (`frequency: "all_time"`). Marginal below total means the channel is on the flattening part of its curve.
- **Response curves** return per channel a spend grid, `median_response`, and lower/upper bands, often downsampled (`transport_curve`) with a compact `sparkline`. Check the units the response reports before quoting spend levels from the grid; if units are unclear, describe the shape (steep, bending, flat) instead of quoting values.
- **Every result** carries `decision_gate` (status and warnings) and `provenance`. When `decision_status` is `rejected`, label the output "descriptive only, model failed diagnostics" and give no spend advice from it.
- **Measurement suggestions** carry `recommendations` with a `priority` and `reason` and may say no single experiment is implied. Report what the tool returns; it does not compute experiment power or globally best designs.

## Keep the quantities apart

- **Contribution** is the modeled share of outcome. It grows with spend, so a big channel can have a big contribution and a poor return.
- **Total iROAS** is the average incremental return on historical spend.
- **Marginal iROAS** is the return on the next unit at today's spend. Budget moves are judged on this one.
- **Response curve** shows where diminishing returns start. Reading far beyond the spend levels seen in history is extrapolation.
- **Predictive evidence** (from validation) shows the model forecasts well. It is separate from causal identification.
- **Causal evidence** needs design: lift tests, geo experiments, holdouts. Calibration with experiments strengthens specific channel claims.

## Marketing interpretation

Use the [marketing decision playbook](marketing://skills/references/marketing-decision-playbook) for vocabulary and profitability framing. The patterns that come up most:

- **Platform ROAS vs model iROAS.** The user's Ads Manager ROAS is attribution-based and usually higher for retargeting and branded search, because those channels collect credit for demand that already existed. Present that gap as expected, and name which number is which.
- **Break-even.** With a revenue target and a user-supplied margin `m`, the next unit of spend pays for itself when marginal iROAS exceeds `1 / m`. Compare the server's marginal iROAS *range* with that line: fully above supports scaling, straddling calls for a measured step or a test, fully below means the channel is past its efficient level at the margin.
- **Headroom.** A channel with high marginal iROAS and a curve that is still steep at current spend is a candidate for more budget. A channel on the flat part is a candidate for trimming. Hand the concrete move to `pymc-budget-optimization` to evaluate.
- **Wide intervals.** Say plainly that the data cannot pin the channel down, and suggest the experiment that would.

Example phrasing: "Across the fitted period, the model estimates Meta returned between X and Y in incremental revenue per unit of spend. At current spend, the next unit returns less, between A and B, which is close to your break-even of C at 40% margin. Scaling Meta further looks marginal until a lift test confirms it."

## Stop conditions

- The model is rejected and the user wants a return figure or a budget answer: stop and route to `pymc-diagnostics-gate`.
- The tool returned an error such as `ANALYSIS_UNAVAILABLE` or `INCREMENTALITY_FAILED`: report it and suggest a refit through `pymc-mmm-workflow`; do not estimate from coefficients or plots.
- The user asks for creative, audience, or daily effects: explain that the MMM does not resolve them.

## Handoff

- Spend change or reallocation: `pymc-budget-optimization` with the `model_id` and the channels in question.
- Uncertainty is decisive: `recommend_next_measurement`, then `pymc-lift-calibration` once results exist.
- Final write-up: [scientific answer contract](marketing://skills/references/scientific-answer-contract).
