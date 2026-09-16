"""Security tests asserting zero secret leakage in normalized errors and MCP responses."""

from __future__ import annotations

import pytest

from marketing_mcp.errors import DomainError, ErrorCategory, NormalizedError
from marketing_mcp.error_boundary import mcp_error_boundary
from marketing_mcp.security.redaction import redact_string, redact_url


class TestErrorSecretLeakagePrevention:
    def test_bearer_token_never_leaks_in_domain_error(self):
        secret_token = "eyJhGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.sflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        err = DomainError(
            code="AUTHENTICATION_FAILED",
            message=f"Failed authenticating with token Bearer {secret_token}",
            evidence={"authorization": f"Bearer {secret_token}"},
        )
        resp = err.to_mcp_response()
        resp_str = str(resp)
        assert secret_token not in resp_str
        assert "[REDACTED]" in resp_str

    def test_signed_url_signatures_redacted(self):
        s3_signed_url = "https://my-bucket.s3.amazonaws.com/dataset.csv?X-Amz-Signature=a1b2c3d4e5f67890abcdef1234567890&X-Amz-Algorithm=AWS4-HMAC-SHA256"
        cleaned_url = redact_url(s3_signed_url)
        assert "a1b2c3d4e5f67890abcdef1234567890" not in cleaned_url
        assert "[REDACTED]" in cleaned_url or "%5BREDACTED%5D" in cleaned_url

        gcs_signed_url = "https://storage.googleapis.com/my-bucket/model.nc?X-Goog-Signature=abcdef1234567890abcdef1234567890"
        cleaned_gcs = redact_url(gcs_signed_url)
        assert "abcdef1234567890abcdef1234567890" not in cleaned_gcs
        assert "[REDACTED]" in cleaned_gcs or "%5BREDACTED%5D" in cleaned_gcs

    def test_database_password_redacted_in_string_and_url(self):
        db_uri = "postgresql://analytics_user:super_secret_db_pass_999@db.internal:5432/marketing_mcp"
        cleaned = redact_string(db_uri)
        assert "super_secret_db_pass_999" not in cleaned
        assert "analytics_user:[REDACTED]@db.internal:5432" in cleaned

    def test_traceback_never_leaks_in_mcp_response(self):
        @mcp_error_boundary("sample_op", "sample_comp", "sample_stage")
        async def failing_tool():
            # Deep call stack
            def _inner():
                raise RuntimeError("something catastrophic failed deeply in the engine")
            _inner()

        import asyncio
        resp = asyncio.run(failing_tool())
        assert "error" in resp
        error_payload = resp["error"]
        # Public response must not leak full traceback lines
        assert "traceback" not in error_payload
        assert "File \"" not in str(error_payload)
        assert "line " not in str(error_payload).lower() or "lineage" in str(error_payload).lower()
        # But error_id is present for operator correlation
        assert "error_id" in error_payload
        assert error_payload["error_id"].startswith("err_")

    def test_api_key_assignment_redacted_in_evidence(self):
        evidence = {
            "config": "MARKETING_MCP_API_KEY=top_secret_prod_key_777",
            "token": "token=abcd99887766",
        }
        err = DomainError(
            code="CONFIGURATION_INVALID",
            message="Invalid configuration provided",
            evidence=evidence,
        )
        d = err.to_dict()
        assert "top_secret_prod_key_777" not in str(d)
        assert "abcd99887766" not in str(d)
        assert "[REDACTED]" in str(d)
