# Google Cloud Deployment

## Status

The repository contains Cloud Run/Docker deployment assets, but the current Cloud Run path is **development/staging only** and is not the approved production topology

Do not describe `scripts/deploy_cloud_run.sh`, `cloudbuild.yaml`, a single Cloud Run instance, SQLite on container/GCS-FUSE storage, or a successful `/health` response as proof of production readiness

Production deployment is blocked by the G2, G3, G4, G5 and H1-H4 requirements in `docs/PRODUCTION-READINESS.md`

## Current deployment path

The current service can run as one Streamable HTTP process

```text
MCP client
  -> Cloud Run / container
  -> marketing-mcp --transport streamable-http
  -> Uvicorn + MCP server
  -> local Application
       -> SQLite metadata
       -> SQLite jobs
       -> local artifacts
       -> in-process AsyncioJobExecutor
       -> PyMC-Marketing
```

This topology can be useful for controlled testing, but it has production limits

- API and statistical compute share the same process/container lifetime
- long-running jobs are not isolated from the API process
- SQLite is the active metadata/job repository
- artifact storage is local-path based
- current ownership/security paths are not yet proven end to end for remote MCP resources
- current release does not have a generated CI evidence pack proving the deployment

## Supported single-instance deployment

`scripts/deploy_cloud_run.sh` deploys the supported single-instance topology described in `docs/OPERATIONS.md`

- `http-private-api-key` profile by default; `--beta` is the only anonymous path and prints a warning
- API key and artifact download-link secret come from Secret Manager (`--set-secrets`)
- `--max-instances 1`, because SQLite runs on instance disk and is snapshotted to the GCS mount (`MARKETING_MCP_METADATA_SNAPSHOT`), which supports one writer
- the bucket has object versioning, so earlier snapshots can be restored
- the container runs as uid 10001 with a `HEALTHCHECK` on `/health/live`

`cloudbuild.yaml` performs the same deploy from CI after the script has created the bucket and secrets once

This is a supported deployment for one tenant or a small set of trusted API-key holders. The multi-instance target topology below still needs a shared SQL backend and is not implemented

Raw credentials must never be printed as deployment output or committed into configuration

## Development Cloud Run example

Use explicit project/environment values rather than repository-specific hardcoded examples

```bash
export GCP_PROJECT_ID="YOUR_PROJECT_ID"
export GCP_REGION="YOUR_REGION"
export MARKETING_MCP_SECURITY_PROFILE="http-private-api-key"
export MARKETING_MCP_API_KEY="YOUR_TEST_KEY"

# Build/deploy using your reviewed staging pipeline
```

Header credentials only

```text
Authorization: Bearer <TOKEN>
X-API-Key: <KEY>
```

Query-string credentials are not supported

## Health endpoints

Current HTTP endpoints include

- `GET /health`: compatibility summary
- `GET /health/live`: process liveness
- `GET /health/ready`: configured application dependency check
- `/mcp`: Streamable HTTP MCP endpoint

A green liveness response only proves that the process is alive

Production readiness must additionally fail when required durable metadata, job-execution, artifact or auth-verifier dependencies are unavailable

## Target production topology

```text
Remote MCP clients
  -> HTTPS / platform ingress
  -> authenticated MCP API service
       -> request Principal + tenant context
       -> scope + object authorization
       -> short read/control operations
       -> durable job submission

MCP API service
  -> PostgreSQL metadata/job repository
  -> object storage for datasets/models/plots
  -> credential verifier / OAuth resource-server integration
  -> structured logs + metrics + traces

Statistical worker service / process pool
  -> durable job claim
  -> heartbeat / cancellation
  -> PyMC-Marketing sampling
  -> immutable artifact write + checksum
  -> transactional job/resource completion

Operations
  -> readiness checks
  -> queue/error alerts
  -> backup/restore
  -> release evidence tied to image digest + git SHA
```

The exact Google Cloud products may change as long as the repository interfaces and release gates are satisfied. The application domain must not depend directly on Cloud Run, Pub/Sub, Cloud SQL or GCS-specific semantics

## Target Google Cloud mapping

A reasonable production mapping is

| Concern | Target property | Possible GCP implementation |
|---|---|---|
| MCP API | short-lived authenticated requests | Cloud Run service |
| Metadata/jobs | durable transactional state | Cloud SQL for PostgreSQL |
| Artifacts | immutable checksum-addressed objects | Cloud Storage |
| Statistical workers | process-isolated CPU-heavy jobs | separate Cloud Run worker/job or equivalent compute pool |
| Credentials | no raw secret persistence in browser/repo | Secret Manager for service secrets, OAuth issuer/resource server for users/clients |
| Logs/traces/metrics | request/job correlation | OpenTelemetry + Cloud Logging/Monitoring or compatible backend |
| Release identity | immutable artifact tied to commit | Artifact Registry digest + OCI labels + release evidence |

This table is target architecture, not a statement that these adapters already exist

## Production authentication target

`http-production-oauth` is the intended remote production posture

Production requirements include

- issuer and audience configured
- token verifier wired into the actual MCP HTTP path
- verified claims mapped to `Principal`
- required scopes enforced at tool execution
- object/tenant ownership enforced for tools and MCP resources
- no query credentials
- no raw browser-generated API-key authority

Private API keys may remain useful for staging or tightly controlled private deployments after the credential-authority hardening plan is complete

## Worker and concurrency policy

Do not set a single universal concurrency value in documentation

API concurrency and statistical worker concurrency solve different problems and must be configured separately

- API service: bounded concurrency for MCP sessions and control/read calls
- statistical workers: admission-controlled concurrency based on CPU, memory and sampler workload
- queue/backpressure: reject or queue work when capacity is exhausted rather than running arbitrary concurrent fits in one API process

No fixed MCMC completion latency is promised across arbitrary datasets/models

## Deployment verification before production

Required release evidence includes

1. build wheel and container from one commit
2. clean-install wheel smoke test
3. container startup and `/health/live` smoke test
4. production-style `/health/ready` dependency failure/success tests
5. real authenticated Streamable HTTP MCP session
6. limited-scope and cross-tenant denial tests
7. job submission, worker execution, cancellation and restart recovery
8. artifact checksum/persistence verification
9. backup/restore test
10. image digest and git SHA recorded in generated release evidence

Until those pass from the release candidate, deployment instructions remain staging guidance

See

- `docs/ARCHITECTURE.md`
- `docs/SECURITY.md`
- `docs/PRODUCTION-READINESS.md`
- `docs/superpowers/plans/2026-08-26-jobs-mcp-task-boundary.md`
- `docs/superpowers/plans/2026-08-26-runtime-truth-ci-gates.md`
