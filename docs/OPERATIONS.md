# Operations Runbook

How to run one production instance of the server, and what to do when something breaks. This covers the supported single-instance topology. Multi-instance deployments need a shared SQL backend, which does not exist yet (see `docs/PRODUCTION-READINESS.md`)

## Supported topology

```text
MCP clients --HTTPS--> Cloud Run (max 1 instance) or one Docker host
                         marketing-mcp --transport streamable-http
                         profile: http-private-api-key
                         SQLite on instance disk  --snapshot-->  durable volume / GCS bucket
                         datasets, models, plots  ------------>  durable volume / GCS bucket
```

Rules that keep this safe

- exactly one instance writes the metadata database. On Cloud Run keep `--max-instances 1`
- the durable volume is mounted at `/var/lib/marketing-mcp`. The database itself stays on local disk at `/var/lib/marketing-mcp-local/metadata.db` because SQLite locking does not work on object storage mounts
- `MARKETING_MCP_METADATA_SNAPSHOT` (image default `/var/lib/marketing-mcp/state/metadata.db`) receives a consistent copy every `MARKETING_MCP_SNAPSHOT_INTERVAL_SECONDS` (default 300) and once more on graceful shutdown. On startup the snapshot is restored when the local database is missing
- worst case after a hard crash: the last interval of metadata writes is lost. Jobs that were running are marked by `recover_stale_running_jobs()` and can be resumed

## Deploy

Cloud Run

```bash
./scripts/deploy_cloud_run.sh            # API-key protected
MIN_INSTANCES=1 ./scripts/deploy_cloud_run.sh   # keep the instance warm (avoids cold starts killing long fits)
```

The script creates the bucket (with object versioning), the Artifact Registry repository and two Secret Manager secrets: `<service>-api-key` and `<service>-token-secret`. Secrets reach the container through `--set-secrets` and are never printed

Single Docker host

```bash
export MARKETING_MCP_API_KEY="$(python3 -c 'import secrets; print("mcp_" + secrets.token_hex(32))')"
export MARKETING_MCP_TOKEN_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
docker compose up -d --build
```

Compose binds to `127.0.0.1:8080`. Put a TLS reverse proxy in front before exposing it

`--beta` / `fast_deploy.sh beta` runs without authentication. Every caller then shares one tenant and can read every stored dataset. Use it only for throwaway demos with synthetic data

## Health checks

| Endpoint | Meaning | Use for |
|---|---|---|
| `GET /health/live` | process is up | container liveness / Docker `HEALTHCHECK` |
| `GET /health/ready` | database and artifact storage respond | load balancer readiness, alerting |
| `GET /health` | version, auth mode, native engine | humans |

## Alerts worth setting

Keep the list short. Each one maps to an action below

1. `/health/ready` returns 503 for more than 2 minutes
2. log lines containing `Metadata snapshot failed` (snapshot is falling behind)
3. HTTP 5xx rate above 5% for 10 minutes
4. container restarts more than 3 times in an hour (usually memory: MCMC fits on large datasets)

On Cloud Run, create these as log-based metrics plus uptime checks in Cloud Monitoring

## Routine tasks

Rotate the API key

```bash
python3 -c 'import secrets; print("mcp_" + secrets.token_hex(32), end="")' |
  gcloud secrets versions add pymc-marketing-mcp-api-key --data-file=-
gcloud run services update pymc-marketing-mcp --region "$GCP_REGION"   # new revision reads :latest
```

Several keys can be active during a rollover: `MARKETING_MCP_API_KEY` accepts a comma-separated list

Rotate the download-link secret the same way with `pymc-marketing-mcp-token-secret`. Existing export links stop working, which is the point

Clean old artifacts: call the `cleanup_server_storage` MCP tool with `dry_run=true` first, then without it

## Backup and restore

The bucket holds everything durable: `state/metadata.db` plus the artifact blobs. Object versioning keeps previous snapshot versions

Restore the metadata to an earlier point

```bash
gcloud storage ls -a gs://$BUCKET/state/metadata.db          # list versions
gcloud storage cp gs://$BUCKET/state/metadata.db#<generation> gs://$BUCKET/state/metadata.db
gcloud run services update pymc-marketing-mcp --region "$GCP_REGION"   # fresh instance restores it
```

The restore refuses a snapshot that fails `PRAGMA integrity_check` and the server will not start. In that case copy an earlier generation as shown above

On a Docker host, back up the two named volumes (`marketing_mcp_data`, `marketing_mcp_db`) with your usual volume backup tooling while the container is stopped, or copy `state/metadata.db` from the data volume at any time

## Incidents

| Symptom | Likely cause | Action |
|---|---|---|
| server exits with `refusing to start` | insecure config (public bind without auth) or bad snapshot | read the message; set the API key secret, or restore an earlier snapshot generation |
| every request returns 401 | secret not mounted or rotated without redeploy | check `--set-secrets` on the revision; redeploy |
| models/datasets disappeared after restart | snapshot path not on the durable mount, or two instances ran at once | confirm `MARKETING_MCP_METADATA_SNAPSHOT` sits under `/var/lib/marketing-mcp`; confirm max instances is 1; restore a snapshot generation |
| export links return 401 | token secret changed or instance restarted without `MARKETING_MCP_TOKEN_SECRET` | set the secret; re-export the artifact |
| fits killed mid-run | instance scaled to zero or ran out of memory | set `MIN_INSTANCES=1`; submit long fits as jobs and resume with `resume_job` |
| API keys issued during a `--beta` period | builds before this runbook let anonymous callers mint keys, and those keys stay valid once auth is on | before enabling auth, stop the server and run `sqlite3 metadata.db "UPDATE credentials SET status='revoked', revoked_at=datetime('now') WHERE owner_subject='anonymous' AND status='active'"` against the database (or its snapshot) |
