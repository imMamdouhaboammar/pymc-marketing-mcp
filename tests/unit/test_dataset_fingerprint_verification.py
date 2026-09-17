from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from marketing_mcp.errors import DomainError
from marketing_mcp.services.decision_service import DecisionService


def test_dataset_fingerprint_lineage_verification():
    """Verify that DecisionService verifies dataset fingerprint integrity before decision execution."""
    metadata = MagicMock()
    modeling = MagicMock()

    service = DecisionService(metadata=metadata, modeling=modeling)

    # 1. Model record with fingerprint fp_initial
    mock_record = MagicMock()
    mock_record.validation_state = "approved"
    mock_record.diagnostics = {"failures": []}
    mock_record.model_id = "mod_123"
    mock_record.dataset_id = "ds_123"
    mock_record.dataset_fingerprint = "sha256_hash_initial"
    mock_record.tenant_id = "tenant_alpha"
    modeling.status.return_value = mock_record
    modeling.load_model.return_value = ("mock_model", mock_record)

    # Dataset in store has identical fingerprint -> PASS
    metadata.get_dataset.return_value = {
        "dataset_id": "ds_123",
        "fingerprint": "sha256_hash_initial",
        "tenant_id": "tenant_alpha",
    }
    model, rec = service._approved("mod_123")
    assert rec == mock_record

    # 2. Dataset in store was mutated (fingerprint changed) -> STRICT REJECTION
    metadata.get_dataset.return_value = {
        "dataset_id": "ds_123",
        "fingerprint": "sha256_hash_MUTATED_DATA",
        "tenant_id": "tenant_alpha",
    }
    with pytest.raises(DomainError) as exc_info:
        service._approved("mod_123")
    assert exc_info.value.code == "DATASET_FINGERPRINT_MISMATCH"
    assert "mutated" in exc_info.value.message.lower()
