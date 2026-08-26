# Verification Coverage Matrix

This matrix describes the current v0.4.0 verification surface and the remaining evidence needed for production release

It deliberately does not use static `PASS` labels for release status. A pass is release evidence only when the corresponding test/workflow is executed for the exact commit and captured under `docs/release-evidence/`

## Scientific and decision behavior

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| Dataset registration/validation | deterministic unit/integration plus real MMM workflows | implemented, strong test coverage | current-head suite evidence |
| Single-dimension MMM fit | real PyMC-Marketing sampling tests | implemented, strong test coverage | current-head statistical evidence |
| Multidimensional MMM | real panel sampling tests | implemented, strong test coverage | current-head statistical evidence |
| Channel-specific transforms | real model-construction tests | implemented, strong test coverage | current-head statistical evidence |
| Diagnostics classification | deterministic thresholds + real MMM use | implemented | current-head contract/statistical evidence |
| Channel contributions | real posterior workflows | implemented | current-head statistical evidence |
| Incremental ROAS | real incrementality workflows + decision-service gate | implemented | capability registry/docs gate alignment + current-head evidence |
| Scenario simulation | exact-scenario statistical workflows | implemented | current-head decision-invariant evidence |
| Budget optimization | constraint/conservation statistical tests | implemented | current-head decision-invariant evidence |
| Dynamic flighting | real carryover/constraint statistical test | implemented | current-head statistical evidence |
| Lift calibration/lineage | real calibration workflow | implemented | current-head statistical evidence |
| Cross-validation | real PyMC-Marketing time-slice workflow | implemented | current-head statistical evidence |
| Prior sensitivity | real library workflow | implemented | current-head statistical evidence |
| Model comparison | real InferenceData/model selection tests | implemented | current-head statistical evidence |
| CLV purchase/value/LTV | real model-specific CLV tests | implemented | current-head statistical evidence |
| Plot summaries | dimension-safe summary tests; plot capability remains experimental | partial | executable evidence for public plot tool/resource contract |

## MCP and application behavior

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| MCP stdio | discovery/round-trip integration tests | implemented | current-head evidence |
| MCP Streamable HTTP | protocol/auth integration tests exist | implemented locally | production-style current-head HTTP evidence |
| Capability inventory | registry checked against MCP discovery and generated docs | implemented | drift checks green on release commit |
| Tool contracts | documented public tool surface | implemented | G0 current-head evidence |
| Model persistence | SQLite metadata + local NetCDF artifacts + restart tests | local implementation | production durable repository/artifact evidence |
| Job API | submit/status/cancel/list with SQLite records | implemented locally | worker/process isolation + recovery evidence |
| Job idempotency | key-based local deduplication primitives | partial | semantic conflict + concurrency + production repository evidence |
| Job restart recovery | stale-job recovery/local repository tests | partial | real running statistical job crash/restart evidence |

## Security

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| Fail-closed HTTP profiles | config/release tests | implemented | real production-profile startup evidence |
| Header-only credentials | middleware/integration tests | implemented | current-head remote evidence |
| Query credential rejection | integration/release tests | implemented | current-head remote evidence |
| Scope policy | tool handler checks + unit tests | implemented in tool modules | prove authenticated HTTP principal reaches those checks |
| Principal propagation | middleware identity and tool contexts exist separately | **not proven end to end** | limited-scope token through real MCP HTTP call |
| Ownership helpers | dataset/model/job authorization helpers exist | implemented as primitives | wire/prove creation and read/mutation lifecycle |
| Cross-tenant tools | helper/job tests | partial | E2E MCP tool denial with real request principal |
| MCP resource authorization | resource handlers currently read storage directly | **blocked** | request-scoped scope/ownership checks for every resource |
| OAuth verifier | verifier + unit coverage | partial | production HTTP runtime integration evidence |
| Secret redaction | error/evidence helpers/tests | implemented | logs/traces/release-evidence redaction tests |
| Dashboard API keys | browser/Firestore prototype stores raw secret material | **blocked for production** | backend-issued verifier-only credentials + real revocation |

## Operability and release

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| Structured logging | foundation/tests exist | partial | request/job context propagation + production output evidence |
| Metrics | collector/foundation exists | partial | request/job/storage metrics + low-cardinality contract |
| Tracing | no complete request-to-job tracing evidence | blocked | OpenTelemetry span propagation across job boundary |
| Liveness | endpoint exists | implemented | container smoke evidence |
| Readiness | local configured dependency checks exist | partial | durable DB/job/artifact/auth dependency readiness |
| Alerts/SLOs | not yet documented/operationalized | blocked | SLO/alert definitions + runbooks |
| PR CI | required workflow not present | blocked | green required PR pipeline |
| Nightly statistical CI | required workflow not present | blocked | scheduled statistical workflow |
| Security/supply-chain CI | required workflow not present | blocked | vulnerability/secret/SBOM policy evidence |
| Upstream compatibility canary | plan exists | blocked | locked/latest-allowed canary workflow |
| Release workflow | collector/helpers exist but no release pipeline | blocked | same-commit wheel/container + hashes/digest evidence |
| Current-head release evidence | only historical baseline exists today | blocked | generated `<sha>.json` and `<sha>.md` from CI |

## Agent quality

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| Skills | domain skills exist | implemented as guidance | map to generated capability registry |
| Router | hardening design exists | partial/not complete | minimal capability-driven routing tests |
| Agent behavior tests | deterministic cases exist | partial | trace-based runner over current tool contracts |
| Negative decision/security evals | some coverage exists | partial | full required pack, including tenant/security/warning cases |
| Eval result integrity | committed fixtures still contain pre-marked success values | blocked | runtime result generation only |

## Historical note

The previous version of this file was a v0.3 snapshot containing fixed sample values, a 17-tool count and static PASS labels. It is retained in Git history only and is not current release evidence

## How to establish a release result

1. run the bounded PR/release checks on the exact candidate commit
2. run the real statistical suite
3. run remote security and durable recovery integration suites
4. build/install wheel and container from the same commit
5. run compatibility canary as required
6. generate the release-evidence JSON/Markdown artifacts
7. only then update `docs/PRODUCTION-READINESS.md` from that evidence
