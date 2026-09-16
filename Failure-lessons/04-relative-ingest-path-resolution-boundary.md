# Post-Mortem 04: Relative Ingest Path Resolution Boundary

## 1. Executive Summary & Context
When users or AI agent clients called `register_dataset` with standard relative filenames (e.g. `path: "valid_clv.csv"`), the server rejected the request with `PATH_NOT_ALLOWED`, even though the file was located in the configured data inbox (`/data/inbox/valid_clv.csv`).

- **Component**: `src/marketing_mcp/security/request_safety.py` (`safe_ingest_path`)
- **Severity**: Medium (Client Usability & Path Confusion)
- **Time to Detect**: First client attempt to ingest a file by simple basename
- **Status**: Resolved & Verified

---

## 2. Symptom & Error Signature
Client received:
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "error": {
    "code": -32000,
    "message": "PATH_NOT_ALLOWED: Path 'valid_clv.csv' is outside the ingest directory '/data/inbox'"
  }
}
```

---

## 3. Root Cause Analysis
In `src/marketing_mcp/security/request_safety.py`:
```python
def safe_ingest_path(path: Path, ingest_root: Path, max_bytes: int) -> Path:
    p = safe_source_path(path, max_bytes) # Calls Path(path).resolve()
    root = Path(ingest_root).resolve()
    try:
        p.relative_to(root)
    except ValueError as e:
        raise DomainError("PATH_NOT_ALLOWED", f"Path '{path}' is outside the ingest directory '{ingest_root}'")
```
When `path` was a relative string like `"valid_clv.csv"`:
1. `Path("valid_clv.csv").resolve()` resolved the relative path against the Python process current working directory (`/app` in Cloud Run container).
2. The resolved path became `/app/valid_clv.csv`.
3. `p.relative_to(Path("/data/inbox"))` evaluated `/app/valid_clv.csv` relative to `/data/inbox`.
4. Because `/app` is completely outside `/data/inbox`, Python raised `ValueError`, which triggered `DomainError("PATH_NOT_ALLOWED")`.

---

## 4. Resolution & Architecture Diff
To support both natural relative basenames (resolved inside `ingest_root`) and explicit subpaths while strictly preventing directory traversal (`../`) attacks:

### Diff in `src/marketing_mcp/security/request_safety.py`:
```python
def safe_ingest_path(path: Path, ingest_root: Path, max_bytes: int) -> Path:
    root = Path(ingest_root).resolve()
+   target = path if path.is_absolute() else (root / path)
+   p = safe_source_path(target, max_bytes)
    try:
        p.relative_to(root)
    except ValueError as e:
        raise DomainError(
            "PATH_NOT_ALLOWED",
            f"Path '{path}' is outside the ingest directory '{ingest_root}'",
        ) from e
    return p
```

---

## 5. Verification & Evidence
- Passing `"valid_clv.csv"` resolves cleanly to `/data/inbox/valid_clv.csv` and succeeds.
- Passing absolute path `/data/inbox/valid_clv.csv` succeeds.
- Traversal attempts like `"../../etc/passwd"` or `"/etc/shadow"` are caught by `p.relative_to(root)` and rejected with `PATH_NOT_ALLOWED`.
