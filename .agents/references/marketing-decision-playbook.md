# Marketing Decision Playbook

Marketers arrive with commercial questions ("where should the next 100k go?"), and this server answers with posterior quantities. This playbook covers both directions: turning the question into the right sequence of server calls, and turning the returned evidence into a recommendation a marketing lead can act on without overstating what the model knows.

The rules in the [agent operating protocol](marketing://skills/references/agent-operating-protocol) and the [scientific answer contract](marketing://skills/references/scientific-answer-contract) still apply. Every model-dependent number comes from a tool result.

## 1. Translate the question before calling anything

| The marketer asks | What they actually need | Server path | What the server cannot answer |
| --- | --- | --- | --- |
| "Which channels are working?" | Modeled share of outcome, plus return per unit of spend | `get_channel_contributions`, then `get_incremental_roas` after an approved diagnosis | Creative, audience, or keyword-level performance |
| "Where should the next dollar go?" | Marginal return at current spend and how much headroom is left | `get_incremental_roas` (marginal iROAS), `get_response_curves`, then `simulate_budget` for the specific move | Channels never run, or spend levels far above anything in history |
| "Cut 20% of budget with the least damage" | A constrained reallocation at a lower total | `optimize_budget` with the reduced `budget` and the user's floors, or `simulate_budget` on specific cuts | Contractual minimums the user has not told you about |
| "Move 30% from TV to Meta, what happens?" | One counterfactual scenario | `simulate_budget` with `percent_change` on the two channels | Whether that move is the best one (that is `optimize_budget`) |
| "Plan Q4 / Ramadan / White Friday week by week" | Timing of spend under carryover | `optimize_flighting` with `pattern` per channel and weekly floors/caps | Events with no comparable history in the data |
| "Is Meta's reported ROAS real?" | A comparison between platform attribution and modeled incrementality | Model iROAS from `get_incremental_roas`; platform ROAS comes from the user | A final verdict; disagreement is expected and a lift test settles it |
| "Should we run a geo test, and where?" | Where uncertainty is costing money | `recommend_next_measurement`, then `pymc-lift-calibration` once results exist | Experiment power calculations beyond what the tool returns |
| "What is a customer worth? What CAC can we afford?" | CLV by customer or segment and a ceiling for acquisition cost | CLV path: purchase model, value model, `estimate_customer_lifetime_value` | A CAC ceiling without the user's margin and payback rules |
| "Did last week's campaign work?" | Short-window causal read | Usually outside MMM; say so and suggest a holdout or lift test | Day-level or single-flight effects in a weekly model |

When a question mixes several rows, answer them in dependency order: data readiness, then fit, then diagnosis, then evidence, then decisions.

## 2. Keep the metric vocabulary distinct

Marketers use "ROAS" for five different numbers. Name which one you are reporting every time.

- **Platform-reported ROAS**: attributed revenue divided by spend, from Meta Ads Manager, Google Ads, TikTok, and similar. It uses click or view windows, counts conversions that would have happened anyway, and overlaps across platforms. The server never produces it.
- **Contribution**: the part of the modeled outcome the MMM assigns to a channel over the fitted period. Descriptive.
- **Total iROAS**: incremental outcome per unit of spend across the evaluated spend level, from `get_incremental_roas`.
- **Marginal iROAS**: incremental outcome from the *next* unit of spend at the current level. Under saturation it sits below total iROAS, sometimes far below. Budget moves should be judged on the marginal figure.
- **Lift-test result**: an experimental estimate for a specific channel, geography, and period. Strongest local evidence available; feeds `calibrate_mmm`.

A quick sanity frame for the user: platform ROAS is usually higher than MMM iROAS for lower-funnel channels (retargeting, branded search) because those channels collect credit for demand that already existed. Present a gap in that direction as expected. A large gap in the opposite direction deserves a data check before anyone acts on it.

## 3. Profitability framing

Revenue iROAS above 1.0 does not mean profit. When the target is revenue and the user gives a gross or contribution margin `m`, the break-even marginal iROAS for revenue is `1 / m` (at 40% margin, the next unit of spend has to return 2.5 units of revenue to pay for itself). This is business arithmetic on the user's own margin; the iROAS value itself still comes from the server.

- Compare the server's marginal iROAS **interval** with the break-even line. If the whole interval sits above, scaling is supported. If it straddles the line, recommend a measured step or a test. If it sits below, the channel is over its efficient spend level at the margin.
- For profit-aware flighting, pass the business inputs to the server through `optimize_flighting.financial` (`kpi_unit`, `revenue_per_outcome`, `gross_margin_rate` or `contribution_margin_rate`) with `objective="maximize_net_profit"`, instead of adjusting outputs afterwards.
- When the target is conversions or leads, ask for value per conversion before talking about profit. Without it, report outcomes per unit of spend and stop there.

## 4. Data setup advice worth giving up front

Good MMM results start with the dataset. Offer this checklist when the user is preparing data:

- **Grain**: weekly rows are the usual choice. Daily data is noisier and rarely adds identification for media effects.
- **History**: the server errors below 52 periods and flags caution below 104. Two or more years lets the model separate seasonality from media.
- **Target**: take it from the source of truth (orders from Shopify or the CRM, qualified leads), never from ad-platform attributed conversions, which would make the model partly re-learn platform attribution.
- **Spend**: one currency across all channels and markets. Convert before registering.
- **Channel granularity**: channels that always move together (for example Meta prospecting and Meta retargeting launched and paused together) cannot be separated. Merge them, or expect `HIGH_CHANNEL_CORRELATION` and wide intervals. Split only where spend varied independently.
- **Controls**: price changes, promotions and discount depth, stock-outs, distribution changes, competitor launches, and macro shocks. Missing controls push their effect into whichever channel happened to move at the same time.
- **Multi-market**: for Egypt, KSA, UAE, Qatar, or other markets in one model, use a long panel with a `geo` column and `dims=["geo"]` so each market keeps its own response.

### Calendar effects in MENA markets

Yearly Fourier seasonality (`yearly_seasonality`) captures patterns that repeat on the Gregorian calendar. Several of the biggest demand swings in the region do not:

- **Ramadan and Eid al-Fitr / Eid al-Adha** move roughly 10 to 11 days earlier each Gregorian year. Add explicit control columns (a Ramadan-week flag, Eid-week flags, or a pre-Eid shopping-week flag) or the model will blur them into media.
- **White Friday / Black Friday** (late November), **11.11**, **back-to-school**, **Saudi National Day** (23 September), **Saudi Founding Day** (22 February), **UAE National Day** (2 December), and **Dubai Shopping Festival** are fixed or near-fixed. Seasonality can absorb them only when they fall in the same week each year; a promo flag is safer.
- Salary-cycle effects (end-of-month spikes common in KSA and Egypt) matter in daily data and mostly vanish in weekly data.

If the user asks for a Ramadan or Q4 flighting plan and the dataset has no control for that event, say that the plan rests on average seasonality and that the event effect is not separately modeled.

## 5. Turning results into a recommendation

Structure every decision answer the same way:

1. **The move**: what to change, by how much, in which weeks or markets.
2. **Confidence**: model decision status (`approved` or `approved_with_caution`), the interval on the expected result, and any channel with `IDENTIFIABILITY_RISK` or `EXTRAPOLATION_RISK`.
3. **Why**: the evidence behind it in one or two sentences (marginal iROAS gap, saturation, carryover).
4. **What could make it wrong**: missing controls, short history, correlated channels, spend outside history.
5. **Next measurement**: the test that would firm up the weakest link, when one exists.

Practical guardrails that keep recommendations safe:

- Prefer staged moves inside historical spend support. The server flags spend above 1.5x a channel's historical 95th percentile as `EXTRAPOLATION_RISK` (current server policy); treat flagged channels as test candidates before scaling further.
- Never recommend putting large budget into a channel the server marks with low confidence (`channel_confidence` of `low_sparse_history`). Suggest a controlled test budget instead.
- When `approved_with_caution` comes back, the decision is allowed, and the caution travels with the recommendation into the final answer.
- If the user pushes back with "just give me the number", give the server's number with its interval and the one-sentence caveat that matters most. Do not drop the interval.

## 6. What an MMM cannot see

Say these limits once, early, when they touch the user's question:

- Creative, audience, placement, and keyword differences inside a channel.
- Day-level or single-campaign effects in a weekly model.
- Brand effects that build over longer than the adstock window (`l_max`).
- Channels that never ran, or spend levels far outside history.
- Causal proof on its own. MMM is observational; experiments and calibration strengthen specific claims.

## 7. Phrasing for a marketing audience

- Lead with the decision and its confidence, then the evidence. Save sampler vocabulary for the appendix; say "the model's convergence checks passed" and keep R-hat and ESS for technical readers.
- Use the server's intervals as ranges in plain language: "the model puts the extra revenue between X and Y".
- Keep "incremental" in every return claim so nobody confuses it with platform ROAS.
- Name the model and dataset IDs at the end so the analysis can be reproduced.
