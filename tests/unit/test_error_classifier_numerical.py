import numpy as np
import pytest
from pathlib import Path
from marketing_mcp.error_classifier import classify_exception
from marketing_mcp.security.request_safety import safe_ingest_path
from marketing_mcp.errors import DomainError

def test_classify_numerical_instability_linalg_error():
    exc = np.linalg.LinAlgError("Matrix is singular and positive definite check failed")
    norm = classify_exception(exc, operation="fit_mmm", component="PyMCAdapter")
    assert norm.code == "NUMERICAL_INSTABILITY"
    assert norm.category == "STATISTICAL"
    assert "scaling" in norm.suggested_action.lower() or "collinear" in norm.suggested_action.lower()

def test_classify_floating_point_or_zero_division():
    exc = FloatingPointError("overflow encountered in exp")
    norm = classify_exception(exc, operation="fit_mmm", component="PyMCAdapter")
    assert norm.code == "NUMERICAL_INSTABILITY"

def test_safe_ingest_path_actionable_guidance_on_client_sandbox(tmp_path):
    outside_path = Path("/mnt/data/dirty_marketing.csv")
    with pytest.raises(DomainError) as exc:
        safe_ingest_path(outside_path, tmp_path, max_bytes=1024*1024)
    assert exc.value.code == "CLIENT_SANDBOX_PATH_NOT_ACCESSIBLE"
    assert exc.value.next_action is not None
    assert "content" in exc.value.next_action or "base64" in exc.value.next_action
