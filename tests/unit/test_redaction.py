"""Unit tests for secrets redaction (Wave 4 Task 8)."""

from __future__ import annotations

from marketing_mcp.security.redaction import redact_secrets, redact_string, safe_error_evidence


class TestRedaction:
    def test_redact_bearer_token_string(self):
        s = "Request failed with Authorization: Bearer secret-token-xyz-12345"
        cleaned = redact_string(s)
        assert "secret-token-xyz-12345" not in cleaned
        assert "[REDACTED]" in cleaned

    def test_redact_jwt_token_string(self):
        jwt_sample = "header.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.signature"
        s = f"Token received: {jwt_sample}"
        cleaned = redact_string(s)
        assert jwt_sample not in cleaned
        assert "[REDACTED]" in cleaned

    def test_redact_nested_dict_sensitive_keys(self):
        payload = {
            "model_id": "mmm-2026-08",
            "auth": {"api_key": "my-secret-key-123", "password": "super-secret-pw"},
            "headers": {"authorization": "Bearer token-abc", "content-type": "application/json"},
            "channels": ["meta", "google"],
            "diagnostics": {"r_hat_max": 1.01},
        }
        cleaned = redact_secrets(payload)
        assert cleaned["model_id"] == "mmm-2026-08"
        assert cleaned["channels"] == ["meta", "google"]
        assert cleaned["diagnostics"]["r_hat_max"] == 1.01
        assert cleaned["auth"]["api_key"] == "[REDACTED]"
        assert cleaned["auth"]["password"] == "[REDACTED]"
        assert cleaned["headers"]["authorization"] == "[REDACTED]"
        assert cleaned["headers"]["content-type"] == "application/json"

    def test_safe_error_evidence(self):
        evidence = {
            "target": "sales",
            "attempted_token": "Bearer fake_token",
            "auth_header": "X-API-Key secret123",
        }
        safe = safe_error_evidence(evidence)
        assert safe["target"] == "sales"
        assert safe["attempted_token"] == "[REDACTED]"
        assert safe["auth_header"] == "[REDACTED]"
