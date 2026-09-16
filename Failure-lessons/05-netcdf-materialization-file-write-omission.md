# Post-Mortem 05: NetCDF Model Materialization File Write Omission

## 1. Executive Summary & Context
After successfully fitting a Bayesian BG/NBD Customer Lifetime Value (CLV) model and saving its posterior trace artifact, subsequent inference queries (`predict_expected_purchases` and `predict_probability_alive`) crashed with `FileNotFoundError: [Errno 2] No such file or directory: .../artifact.nc`.

- **Component**: `src/marketing_mcp/storage/artifacts.py` (`LocalArtifactStore.materialize`)
- **Severity**: High (Model Evaluation & Inference Pipeline Breakdown)
- **Time to Detect**: First post-fit prediction query
- **Status**: Resolved & Verified in Production

---

## 2. Symptom & Error Signature
Server traceback during `predict_expected_purchases`:
```text
Traceback (most recent call last):
  File ".../marketing_mcp/tools/clv_tools.py", line 142, in predict_expected_purchases
    with app.artifacts.materialize(model_ref, suffix=".nc") as model_file:
      model = app.clv.load_model(model_file)
  File ".../pymc_marketing/clv/models/basic.py", line 287, in load
    idata = az.from_netcdf(filename)
  File ".../arviz/data/io_netcdf.py", line 42, in from_netcdf
    return xr.open_dataset(filename, engine="netcdf4")
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/marketing-mcp-artifact-xyz/artifact.nc'
```

---

## 3. Root Cause Analysis
In `LocalArtifactStore.materialize()`:
The method provides a context manager that loads the artifact's raw binary data from disk/GCS and presents it as a concrete filesystem path (required by ArviZ/NetCDF C libraries).
During a refactor of temporary directory handling:
```python
    @contextmanager
    def materialize(self, ref: str, suffix: str = "") -> Iterator[Path]:
        data = self.get_bytes(ref)
        with tempfile.TemporaryDirectory(prefix="marketing-mcp-artifact-") as directory:
            path = Path(directory) / f"artifact{suffix}"
            # BUG: path.write_bytes(data) was missing!
            try:
                path.chmod(0o600)
            except OSError:
                pass
            yield path
```
The file path was computed and passed to the caller, but `path.write_bytes(data)` was omitted. Because no file existed at that path, ArviZ crashed trying to open non-existent bytes.

---

## 4. Resolution & Architecture Diff
We restored the byte-writing step before yielding the path to the caller:

### Diff in `src/marketing_mcp/storage/artifacts.py`:
```python
    @contextmanager
    def materialize(self, ref: str, suffix: str = "") -> Iterator[Path]:
        data = self.get_bytes(ref)
        with tempfile.TemporaryDirectory(prefix="marketing-mcp-artifact-") as directory:
            path = Path(directory) / f"artifact{suffix}"
+           path.write_bytes(data)
            try:
                path.chmod(0o600)
            except OSError:
                pass
            yield path
```

---

## 5. Verification & Evidence
- Model loaded successfully via ArviZ `from_netcdf`.
- Predictions returned expected purchase counts and probability-alive estimates over customer cohorts.
- Temporary files and directories were automatically cleaned up upon context manager exit without storage leaks.
