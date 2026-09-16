# Post-Mortem 08: 1GB Large Artifact Streaming, HTTP Range Requests & Cloud Run RAM Limits

## 1. Executive Summary & Context
Processing enterprise Bayesian Marketing Mix Models (MMM) and Customer Lifetime Value (CLV) traces generates high-dimensional posterior samples, ArviZ `InferenceData` objects, and NetCDF (`.nc`) files ranging from 100MB to over 1GB. When deployed on Google Cloud Run, attempting to serialize and deliver these artifacts directly inside MCP JSON-RPC responses caused immediate `HTTP 413 Payload Too Large` failures and container Out-Of-Memory (`OOM`) crashes.

- **Component**: `src/marketing_mcp/storage/artifacts.py`, `src/marketing_mcp/http/artifacts.py`
- **Severity**: P0 Blocker (Data Transfer & Container Crash)
- **Status**: Resolved & Verified with Test Suite

---

## 2. Symptom & Error Signature
1. **Cloud Run Payload Limits**:
   ```text
   HTTP/1.1 413 Request Entity Too Large
   Content-Length: 33554432
   Connection: close
   ```
   Cloud Run enforces a strict 32MB payload limit on HTTP/1.1 and Server-Sent Events (SSE) responses. Sending traces inside JSON-RPC tool results crashed the stream.

2. **Container OOM on `/tmp`**:
   ```text
   Container terminated with exit code 137 (OOMKilled)
   Memory limit of 8192 MiB exceeded.
   ```
   Cloud Run mounts `/tmp` as an in-memory `tmpfs` RAM disk. Copying or materializing multi-gigabyte `.nc` files into `/tmp` consumed container RAM directly.

---

## 3. Root Cause Analysis
- **Full In-Memory Buffering**: `LocalArtifactStore.put()` and `get()` relied on `.read_bytes()`, loading entire multi-gigabyte blobs into Python memory buffers.
- **Copy-Based Materialization**: `materialize()` created physical file copies in `/tmp`, exhausting container RAM.
- **Lack of Streaming HTTP Transport**: The MCP server had no external HTTP streaming endpoint supporting chunked transfer encoding or resumable HTTP Range requests.

---

## 4. Resolution & Architecture Diff
1. **Chunked Stream Hashing & Reading**:
   Implemented `read_chunks(chunk_size=1024*1024)` and `put_stream()` in `storage/artifacts.py` to stream and hash data in 1MB increments without exceeding memory limits.

2. **Zero-RAM Symlink Materialization**:
   Updated `materialize()` to create filesystem symbolic links (`symlink_to`) pointing directly to storage blobs, eliminating RAM overhead on `tmpfs`.

3. **Resumable HTTP Range Streaming Endpoint**:
   Created `GET /artifacts/{namespace}/{digest}/download` in `http/artifacts.py` supporting `Range: bytes=start-end` and `206 Partial Content` headers for resumable downloads.

4. **Signed Cloud Storage URLs**:
   Added `generate_signed_url()` to offload bulk artifact downloads directly to Google Cloud Storage.

```python
# src/marketing_mcp/storage/artifacts.py
def read_chunks(self, digest: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    path = self._blob_path(digest)
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            yield chunk

@contextmanager
def materialize(self, digest: str) -> Iterator[Path]:
    source = self._blob_path(digest)
    with tempfile.TemporaryDirectory(prefix="mcp-mat-") as tmpdir:
        symlink_target = Path(tmpdir) / f"{digest}.bin"
        symlink_target.symlink_to(source.resolve())
        yield symlink_target
```

---

## 5. Verification & Evidence
- `tests/integration/test_large_artifacts_and_resilience.py::test_large_artifact_chunked_streaming_and_symlink`
- `tests/integration/test_large_artifacts_and_resilience.py::test_artifact_download_http_range_requests`
Both tests passed successfully, verifying chunked stream integrity and HTTP 206 Partial Content response parsing.
