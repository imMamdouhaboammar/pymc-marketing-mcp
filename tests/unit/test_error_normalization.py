"""Comprehensive unit tests for error normalization architecture."""

from __future__ import annotations

import sqlite3
import urllib.error

import pytest
from pydantic import BaseModel, Field, ValidationError

from marketing_mcp.error_boundary import mcp_error_boundary
from marketing_mcp.error_classifier import classify_exception, extract_cause_chain
from marketing_mcp.errors import (
    ERROR_CATALOG,
    DomainError,
    ErrorCategory,
    ErrorSeverity,
    NormalizedError,
    generate_error_id,
    get_error_definition,
)
from marketing_mcp.observability.errors import GLOBAL_ERROR_REGISTRY, ErrorDiagnosticRegistry


class DummySchema(BaseModel):
    name: str
    age: int = Field(gt=0)


class TestErrorTaxonomyAndCatalog:
    def test_generate_error_id_format(self):
        eid1 = generate_error_id()
        eid2 = generate_error_id()
        assert eid1.startswith("err_")
        assert eid2.startswith("err_")
        assert len(eid1) >= 16
        assert eid1 != eid2

    def test_error_catalog_completeness(self):
        assert len(ERROR_CATALOG) >= 80
        for code, definition in ERROR_CATALOG.items():
            assert isinstance(definition.category, ErrorCategory)
            assert isinstance(definition.severity, ErrorSeverity)
            assert isinstance(definition.retryable, bool)
            assert isinstance(definition.user_actionable, bool)
            assert isinstance(definition.http_status, int)
            assert 400 <= definition.http_status <= 599

    def test_get_error_definition_fallback(self):
        defn = get_error_definition("NON_EXISTENT_ERROR_CODE_XYZ")
        assert defn.category == ErrorCategory.INTERNAL
        assert defn.severity == ErrorSeverity.ERROR
        assert defn.retryable is False
        assert defn.http_status == 500

    @pytest.mark.parametrize(
        "code",
        [
            "LONG_TERM_MULTIPLIER_UNDEFINED",
            "LONG_TERM_UNCERTAINTY_REQUIRED",
            "LONG_TERM_GATE_REJECTED",
        ],
    )
    def test_long_term_scientific_errors_are_canonical_and_actionable(self, code):
        defn = get_error_definition(code)
        assert defn.category == ErrorCategory.STATISTICAL
        assert defn.http_status == 422
        assert defn.user_actionable is True
        assert defn.suggested_action


class TestDomainErrorNormalization:
    def test_domain_error_preserves_legacy_and_enriched_fields(self):
        err = DomainError(
            code="MODEL_NOT_FOUND",
            message="Model 'mmm_123' does not exist",
            evidence={"model_id": "mmm_123"},
            next_action="Verify model ID or fit a new model",
        )
        resp = err.to_dict()
        assert "error" in resp
        d = resp["error"]
        assert d["code"] == "MODEL_NOT_FOUND"
        assert d["message"] == "Model 'mmm_123' does not exist"
        assert d["evidence"]["model_id"] == "mmm_123"
        assert d["next_action"] == "Verify model ID or fit a new model"
        assert d["category"] == "MODELING"
        assert "error_id" in d
        assert d["error_id"].startswith("err_")
        assert "timestamp" in d
        assert d["retryable"] is False
        assert d["user_actionable"] is True

    def test_domain_error_to_mcp_response(self):
        err = DomainError("OPTIMIZATION_FAILED", "Budget optimizer failed")
        resp = err.to_mcp_response()
        assert "error" in resp
        assert resp["error"]["code"] == "OPTIMIZATION_FAILED"
        assert resp["error"]["message"] == "Budget optimizer failed"
        assert resp["error"]["category"] == "OPTIMIZATION"


class TestExceptionClassifier:
    def test_classify_domain_error(self):
        dom = DomainError("DATASET_NOT_FOUND", "Dataset 'd1' missing", evidence={"dataset_id": "d1"})
        norm = classify_exception(dom, operation="inspect_dataset", component="datasets")
        assert norm.code == "DATASET_NOT_FOUND"
        assert norm.category == ErrorCategory.DATASET.value
        assert norm.evidence["dataset_id"] == "d1"
        assert norm.retryable is False

    def test_classify_pydantic_validation_error(self):
        try:
            DummySchema(name="test", age=-5)
        except ValidationError as exc:
            norm = classify_exception(exc, operation="validate_schema", component="schemas")
            assert norm.code == "INPUT_INVALID"
            assert norm.category == ErrorCategory.INPUT.value
            assert norm.user_actionable is True
            assert "validation_errors" in norm.evidence
            assert norm.original_error is not None
            assert norm.original_error.type == "ValidationError"

    def test_classify_sqlite_locked(self):
        exc = sqlite3.OperationalError("database is locked")
        norm = classify_exception(exc, operation="update_record", component="database")
        assert norm.code == "PERSISTENCE_WRITE_FAILED"
        assert norm.category == ErrorCategory.PERSISTENCE.value
        assert norm.retryable is True

    def test_classify_sqlite_integrity_error(self):
        exc = sqlite3.IntegrityError("UNIQUE constraint failed: models.model_id")
        norm = classify_exception(exc, operation="save_model", component="database")
        assert norm.code == "PERSISTENCE_WRITE_FAILED"
        assert norm.category == ErrorCategory.PERSISTENCE.value
        assert norm.retryable is False

    def test_classify_http_error(self):
        url = "https://example.com/data.csv"
        exc = urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        norm = classify_exception(exc, operation="fetch_dataset", component="security")
        assert norm.code == "UPSTREAM_HTTP_ERROR"
        assert norm.category == ErrorCategory.NETWORK.value
        assert norm.evidence["status_code"] == 404
        assert norm.original_error is not None
        assert norm.original_error.code == 404

    def test_classify_timeout_error(self):
        exc = TimeoutError("Connection timed out after 30s")
        norm = classify_exception(exc, operation="fetch_remote", component="network")
        assert norm.code == "UPSTREAM_TIMEOUT"
        assert norm.category == ErrorCategory.TIMEOUT.value
        assert norm.retryable is True

    def test_classify_file_not_found(self):
        exc = FileNotFoundError("No such file: /tmp/missing.nc")
        norm = classify_exception(exc, operation="load_artifact", component="storage")
        assert norm.code == "FILE_NOT_FOUND"
        assert norm.category == ErrorCategory.DATASET.value
        assert norm.retryable is False

    def test_classify_unexpected_runtime_error(self):
        exc = RuntimeError("internal matrix inversion crashed")
        norm = classify_exception(exc, operation="sample_mcmc", component="sampling")
        assert norm.code == "INTERNAL_ERROR"
        assert norm.category == ErrorCategory.INTERNAL.value
        assert norm.retryable is False
        assert norm.original_error is not None
        assert norm.original_error.type == "RuntimeError"

    def test_extract_cause_chain(self):
        try:
            try:
                raise ValueError("root level failure")
            except ValueError as root_err:
                raise RuntimeError("wrapped failure") from root_err
        except RuntimeError as top_err:
            chain = extract_cause_chain(top_err)
            assert len(chain) == 1
            assert chain[0].type == "ValueError"
            assert "root level failure" in chain[0].message


class TestErrorBoundaryDecorator:
    @pytest.mark.anyio
    async def test_boundary_success(self):
        @mcp_error_boundary("test_op", "test_comp", "test_stage")
        async def sample_tool(x: int):
            return {"result": x * 2}

        res = await sample_tool(21)
        assert res == {"result": 42}

    @pytest.mark.anyio
    async def test_boundary_catches_domain_error(self):
        @mcp_error_boundary("sample_op", "sample_comp", "sample_stage")
        async def failing_tool():
            raise DomainError("MODEL_NOT_FOUND", "Failing as expected")

        res = await failing_tool()
        assert "error" in res
        err = res["error"]
        assert err["code"] == "MODEL_NOT_FOUND"
        assert err["category"] == "MODELING"
        assert err["error_id"].startswith("err_")

        # Verify recorded in registry
        rec = GLOBAL_ERROR_REGISTRY.lookup(err["error_id"])
        assert rec is not None
        assert rec["code"] == "MODEL_NOT_FOUND"

    @pytest.mark.anyio
    async def test_boundary_catches_unhandled_exception(self):
        @mcp_error_boundary("broken_op", "broken_comp", "broken_stage")
        async def crashing_tool():
            raise KeyError("missing_config_key")

        res = await crashing_tool()
        assert "error" in res
        err = res["error"]
        assert err["code"] in ("CONFIGURATION_INVALID", "INTERNAL_ERROR", "INVALID_ARGUMENT")
        assert "error_id" in err


class TestDiagnosticRegistry:
    def test_registry_lru_and_lookup(self):
        registry = ErrorDiagnosticRegistry(max_size=3)
        err1 = NormalizedError(error_id="err_001", code="E1", message="m1", category=ErrorCategory.INTERNAL)
        err2 = NormalizedError(error_id="err_002", code="E2", message="m2", category=ErrorCategory.INTERNAL)
        err3 = NormalizedError(error_id="err_003", code="E3", message="m3", category=ErrorCategory.INTERNAL)
        err4 = NormalizedError(error_id="err_004", code="E4", message="m4", category=ErrorCategory.INTERNAL)

        registry.record(err1)
        registry.record(err2)
        registry.record(err3)
        assert len(registry) == 3
        assert registry.lookup("err_001") is not None

        # Insert 4th, err_001 should be evicted
        registry.record(err4)
        assert len(registry) == 3
        assert registry.lookup("err_001") is None
        assert registry.lookup("err_004") is not None

    def test_cli_lookup_error(self, monkeypatch, capsys):
        from marketing_mcp.cli import main
        from marketing_mcp.observability.errors import GLOBAL_ERROR_REGISTRY
        test_err = NormalizedError(
            error_id="err_test_cli_123",
            code="TEST_CODE",
            message="CLI diagnostic test message",
            category=ErrorCategory.INTERNAL,
        )
        GLOBAL_ERROR_REGISTRY.record(test_err)

        monkeypatch.setattr("sys.argv", ["marketing-mcp", "lookup-error", "err_test_cli_123"])
        main()
        captured = capsys.readouterr()
        assert "err_test_cli_123" in captured.out
        assert "TEST_CODE" in captured.out
