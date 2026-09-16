# Post-Mortem 11: Artifact Sandbox Push & Server Garbage Collection

## 1. Executive Summary & Context
In cloud-native serverless deployments, disk space and in-memory scratch storage (`tmpfs`) are finite. Running multiple Bayesian models produces gigabytes of NetCDF traces, intermediate data samples, and debug plots. Without proactive lifecycle reclamation, warm containers accumulated obsolete files, leading to disk quota exhaustion. Additionally, AI clients operating inside sandboxes needed a reliable method to pull artifacts directly into their local execution environment for downstream presentation to the end-user.

- **Component**: `src/marketing_mcp/storage/gc.py`, `src/marketing_mcp/mcp/tools/artifacts.py`, `scripts/deploy_cloud_run.sh`
- **Severity**: High (Disk Exhaustion & Sandbox Isolation Boundary)
- **Status**: Resolved & Verified with Test Suite

---

## 2. Symptom & Error Signature
1. **Server Disk Exhaustion**:
   ```text
   OSError: [Errno 28] No space left on device
   Failed to write posterior predictive NetCDF trace.
   ```
   Orphaned files in `/tmp/marketing-mcp-*` and expired temporary datasets consumed the container's storage limit.

2. **Sandbox Data Isolation**:
   The AI client could see artifact digests (e.g. `sha256:abc...`), but had no integrated mechanism or shell commands to fetch, verify, and load the 1GB trace directly into its local environment for the end-user.

---

## 3. Root Cause Analysis
- **Absence of Server Garbage Collection**: The server lacked a garbage collector to sweep `/tmp/` directories, unreferenced binary blobs, and expired delivered artifacts.
- **Missing Push-to-Sandbox Contract**: No MCP tool provided the client with self-contained download commands (`curl`), SHA256 checksums, and Python loading code tailored for the client's local sandbox.

---

## 4. Resolution & Architecture Diff
1. **Sandbox Export Tool (`export_artifact_to_sandbox`)**:
   Empowers the AI client with:
   - Direct download URL (`/artifacts/{namespace}/{digest}/download`)
   - Pre-formatted, resumable `curl` command (`curl -L -C - -o trace.nc ...`)
   - SHA256 checksum verification command (`echo "<hash> trace.nc" | sha256sum -c`)
   - Python snippet to load with ArviZ (`az.from_netcdf("trace.nc")`)

2. **Automated Storage Garbage Collector (`StorageGarbageCollector`)**:
   Implemented in `src/marketing_mcp/storage/gc.py`:
   - Purges `/tmp/marketing-mcp-*` scratch directories.
   - Cleans up artifacts marked as `delivered` once their retention period expires.
   - Identifies and prunes orphaned binary blobs not referenced by any active job or dataset.
   - Exposed to operators and AI clients via `cleanup_server_storage`.

3. **Cloud Storage Lifecycle Policies**:
   Configured automated 7-day TTL rules for temporary files on Google Cloud Storage in `scripts/fast_deploy.sh` and `scripts/deploy_cloud_run.sh`.

```python
# src/marketing_mcp/storage/gc.py
class StorageGarbageCollector:
    def purge_tmp_directories(self) -> int:
        count = 0
        for p in Path("/tmp").glob("marketing-mcp-*"):
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                count += 1
        return count
```

---

## 5. Verification & Evidence
- `tests/integration/test_large_artifacts_and_resilience.py::test_export_artifact_to_sandbox_and_cleanup`
Verified that artifacts are exported with complete sandbox curl and Python instructions, and that server cleanup correctly purges temporary scratch files and unreferenced artifacts.
