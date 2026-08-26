# Verification Coverage Matrix

This matrix describes the current v0.4.0 verification surface and the release evidence structure for the repository

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
| MCP stdio | discovery/round-trip integration tests | verified | current-head evidence |
| MCP Streamable HTTP | protocol/auth integration tests | verified | production-style current-head HTTP evidence |
| Capability inventory | registry checked against MCP discovery and generated docs | verified (0 drift) | drift checks green on release commit |
| Tool contracts | documented public tool surface | verified | G0 current-head evidence |
| Model persistence | SQLite metadata + local NetCDF artifacts + restart tests | verified | production durable repository/artifact evidence |
| Job API | submit/status/cancel/list with SQLite records | verified | worker/process isolation + recovery evidence |
| Job idempotency | canonical semantic hashing + deduplication | verified | semantic conflict + concurrency evidence |
| Job restart recovery | stale-job recovery/local repository tests | verified | real running statistical job crash/restart evidence |

## Security

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| Fail-closed HTTP profiles | config/release tests | verified | real production-profile startup evidence |
| Header-only credentials | middleware/integration tests | verified | current-head remote evidence |
| Query credential rejection | integration/release tests | verified | current-head remote evidence |
| Scope policy | tool handler checks + unit tests | verified | proven via request-scoped context provider |
| Principal propagation | request-scoped context provider (`ContextVar[ExecutionContext]`) | verified | verified in `test_h1_identity_propagation.py` |
| Ownership helpers | dataset/model/job authorization helpers | verified | wired into `AuthorizationService` and storage metadata |
| Cross-tenant tools | helper/job tests | verified | E2E MCP tool denial with real request principal |
| MCP resource authorization | resource handlers enforce scope and tenant authorization | verified | verified in `test_h2_object_isolation.py` & `test_mcp_resource_authorization.py` |
| OAuth verifier | verifier + unit coverage + HTTP integration | verified | verified in `test_g3_remote_security.py` |
| Secret redaction | error/evidence helpers/tests | verified | logs/traces/release-evidence redaction tests |
| Dashboard API keys | backend `CredentialService` with salted SHA-256 verifiers | verified | verified in `test_h3_credential_control_plane.py` |

## Operability and release

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| Structured logging | single-line JSON formatter with secret scrubbing | verified | verified in `test_g4_observability_ci.py` |
| Metrics | collector with low-cardinality counters/gauges | verified | request/job/storage metrics + low-cardinality contract |
| Tracing | distributed trace context propagation (`trace_span`) | verified | trace spans and IDs across request/job boundaries |
| Liveness | endpoint exists (`/health/live`) | verified | container smoke evidence |
| Readiness | dependency readiness probe (`/health/ready`) | verified | durable DB/job/artifact dependency readiness |
| Alerts/SLOs | documented operational invariants | partial | SLO/alert definitions + runbooks |
| PR CI | CI workflow in `.github/workflows/ci.yml` | verified | green PR pipeline |
| Nightly statistical CI | statistical workflow in `.github/workflows/statistical.yml` | verified | scheduled statistical workflow |
| Security/supply-chain CI | security workflow in `.github/workflows/security.yml` | verified | vulnerability/secret/policy evidence |
| Upstream compatibility canary | canary script & workflow in `.github/workflows/upstream-canary.yml` | verified | locked/latest-allowed canary workflow |
| Release workflow | release workflow in `.github/workflows/release.yml` | verified | same-commit wheel/container + hashes/digest evidence |
| Current-head release evidence | machine-collected evidence under `docs/release-evidence/` | verified | generated `<sha>.json` and `<sha>.md` |

## Agent quality

| Area | Current implementation/evidence | Current status | Release requirement |
|---|---|---|---|
| Skills | domain skills in `.agents/skills/` | verified | map to generated capability registry |
| Router | capability-aware engineering routing | verified | minimal capability-driven routing tests |
| Agent behavior tests | deterministic cases in `tests/release/test_h5_agent_skill_evals.py` | verified | trace-based runner over current tool contracts |
| Negative decision/security evals | negative security and diagnostic gate coverage | verified | full required pack, including tenant/security/warning cases |
| Eval result integrity | no pre-marked pass values in eval fixtures | verified | runtime result generation only |

## Historical note

Earlier versions of this file from v0.3 snapshots are retained in Git history only and are not current release evidence

## How to establish a release result

1. run the bounded PR/release checks on the exact candidate commit
2. run the real statistical suite
3. run remote security and durable recovery integration suites
4. build/install wheel and container from the same commit
5. run compatibility canary as required
6. generate the release-evidence JSON/Markdown artifacts
7. validate `docs/PRODUCTION-READINESS.md` with `scripts/render_production_readiness.py --check`
