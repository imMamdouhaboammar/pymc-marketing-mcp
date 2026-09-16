# Post-Mortem 07: Remote Client Sandbox Data Ingestion & Diagnostic Usability

## 1. Executive Summary & Context
When interacting with the remote `pymc-marketing-mcp` Cloud Run instance from AI client sessions (such as Claude.ai web/mobile chat or remote agent harnesses), `register_dataset` was completely non-functional. Calling `register_dataset` with client sandbox paths (e.g. `/mnt/user-data/uploads/complex_ads_sample_data.csv`), relative paths, or URLs consistently returned a byte-for-byte identical error:
`{"code": "DATASET_NOT_FOUND", "message": "Dataset file does not exist", "evidence": null, "next_action": null}`.

Because all downstream MMM and CLV tools require a valid `dataset_id` produced by `register_dataset`, approximately 90% of the connector's tool surface was rendered untestable and unusable for end-users and independent evaluators.

- **Component**: `src/marketing_mcp/mcp/tools/datasets.py`, `src/marketing_mcp/services/dataset_service.py`, `src/marketing_mcp/security/request_safety.py`, `src/marketing_mcp/storage/metadata.py`
- **Severity**: P0 / Blocker
- **Time to Detect**: First evaluation of the remote Cloud Run endpoint with user-uploaded CSV files
- **Status**: Resolved & Verified in Production

---

## 2. Symptom & Error Signature
Across multiple distinct input shapes:
1. `register_dataset(path="/mnt/user-data/uploads/complex_ads_sample_data.csv")`
2. `register_dataset(path="complex_ads_sample_data.csv")`
3. `register_dataset(path="https://example.com/nonexistent.csv")`

Every single invocation failed with:
```json
{
  "error": {
    "code": "DATASET_NOT_FOUND",
    "message": "Dataset file does not exist",
    "evidence": null,
    "next_action": null
  }
}
```
Key issues:
- Zero differentiation between "client sandbox path", "file not found on server", "unsupported URL", or "network failure".
- `evidence` and `next_action` fields were completely empty (`null`), leaving LLM callers unable to self-correct.
- The input path was never echoed back in the error message.
- Multi-ID tools (`compare_models`, `select_best_model`) failed only on the first invalid ID instead of batch-validating the full input list.

---

## 3. Root Cause Analysis
1. **Physical Filesystem Isolation**:
   The MCP server runs inside a Google Cloud Run container. Claude.ai chat sessions run in an Anthropic-managed cloud sandbox with local uploads at `/mnt/user-data/uploads/`. A path string on the client sandbox has zero correspondence to the remote container's filesystem.
2. **Path-Only Tool Signature**:
   `register_dataset(path: str)` strictly expected a pre-existing file on the server's local or FUSE-mounted drive. It provided no parameter to receive raw file contents (`content`), binary base64 bytes (`content_base64`), or streamable remote URLs (`url`).
3. **Flat Error Mapping**:
   In `safe_source_path(path)`:
   `if not p.is_file(): raise DomainError("DATASET_NOT_FOUND", "Dataset file does not exist")`
   Any path that did not exist on the local disk was masked under a single generic exception without context, attempted path, or remediation advice.
4. **Metadata Lookup Omission**:
   `SQLiteMetadataStore._get` raised generic `DomainError(code, f"{key} was not found")` without attaching `evidence` or `next_action`.

---

## 4. Resolution & Architecture Diff

### 4.1 Direct Content Ingestion (`DatasetService.register_bytes`)
Added `register_bytes` in `src/marketing_mcp/services/dataset_service.py` to accept raw byte buffers directly from MCP tool payloads:
```python
    def register_bytes(
        self,
        raw: bytes,
        format: str = "csv",
        filename: str | None = None,
        principal: Any = None,
    ) -> DatasetRegistration:
        # Validates size, computes SHA-256 fingerprint, persists to LocalArtifactStore,
        # registers in SQLite metadata, and returns DatasetRegistration
```

### 4.2 Multi-Modal Tool Interface (`register_dataset`)
Upgraded `register_dataset` in `src/marketing_mcp/mcp/tools/datasets.py` to prioritize direct data channels:
1. `content: str`: Direct CSV string transmitted in the MCP tool call (optimal for chat sandbox sessions).
2. `content_base64: str`: Base64-encoded bytes (optimal for binary Parquet or compressed CSV).
3. `url: str`: Streamable HTTP/HTTPS URL fetched by Cloud Run with robust network and HTTP error handling.
4. `path: str`: Server-local file path (with intelligent sandbox path detection and clear recovery hints).

### 4.3 Sandbox Path Detection & Diagnostic Enrichment
In `src/marketing_mcp/security/request_safety.py`:
```python
    if not p.is_file():
        path_str = str(path)
        is_client_sandbox = any(
            path_str.startswith(prefix) for prefix in ("/mnt/user-data", "/mnt/data", "/home/sandbox")
        ) or any(path_str.startswith(drive) for drive in ("C:", "D:", "/Users/"))
        if is_client_sandbox:
            raise DomainError(
                "CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE",
                f"Path '{path}' is located in a client sandbox or local environment. Remote MCP servers cannot access client files directly.",
                evidence={"attempted_path": path_str},
                next_action="Pass the dataset content directly to register_dataset via 'content' (raw CSV text) or 'content_base64' (base64 string), or provide a downloadable HTTP(S) URL via 'url'.",
            )
```

### 4.4 Data Discovery Tool (`list_datasets`)
Added `list_datasets` tool returning:
- All registered datasets in metadata (`dataset_id`, `rows`, `format`, `created_at`, `fingerprint`).
- All candidate files currently residing in the server's data inbox (`name`, `size_bytes`).

### 4.5 Batch Validation in Model Comparison
In `compare_models` and `select_best_model`:
```python
    missing = []
    for mid in input.model_ids:
        try:
            model_rec = app.metadata.get_model(mid)
            authorize_model(principal, model_rec, action="read")
        except DomainError:
            missing.append(mid)
    if missing:
        raise DomainError(
            "MODEL_NOT_FOUND",
            f"Model(s) not found: {', '.join(missing)}",
            evidence={"missing_model_ids": missing, "provided_model_ids": input.model_ids},
            next_action="Verify model IDs using get_model_status or fit models first using fit_mmm",
        )
```

---

## 5. Verification & Evidence
- **Multi-Platform Complex Dataset**:
  Generated and tested `complex_ads_sample_data.csv` (3000 rows x 71 columns, 6 platforms, 5 countries, realistic data quality flags):
  - Ingestion via `content` passed in 3.70s.
  - Ingestion via `content_base64` passed.
  - `inspect_dataset` correctly identified `revenue_usd` target and all platform spend channels.
- **Client Sandbox Guard**:
  Tested `/mnt/user-data/uploads/complex_ads_sample_data.csv` -> cleanly returned `CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE` with populated `evidence` and `next_action`.
- **Batch Model Validation**:
  Tested `["mdl_fake_1", "mdl_fake_2", "mdl_fake_3"]` -> all 3 reported in single batch error response.
- **Contract Baseline**:
  All 45 contract tests and 37 platform tests pass green.
