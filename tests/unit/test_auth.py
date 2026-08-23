from starlette.datastructures import Headers, QueryParams

from marketing_mcp.auth import (
    APIKeyValidator,
    AuthManager,
    JWTValidator,
    create_jwt_token,
    generate_api_key,
)


class TestAPIKeyValidator:
    def test_generate_api_key(self):
        key1 = generate_api_key()
        key2 = generate_api_key()
        assert key1.startswith("mcp_live_")
        assert key2.startswith("mcp_live_")
        assert key1 != key2
        assert len(key1) > 40

    def test_api_key_validation_success(self):
        val = APIKeyValidator(["valid-key-123", "another-key"])
        ctx = val.validate("valid-key-123")
        assert ctx is not None
        assert ctx.authenticated is True
        assert ctx.auth_type == "api_key"

    def test_api_key_validation_failure(self):
        val = APIKeyValidator(["valid-key-123"])
        assert val.validate("wrong-key") is None
        assert val.validate("") is None


class TestJWTValidator:
    def test_create_and_validate_jwt(self):
        secret = "test-secret-key-1234567890123456"
        token = create_jwt_token(
            secret=secret,
            client_id="claude-desktop",
            scopes=["mcp:read", "mcp:write"],
            expires_in_seconds=3600,
        )
        validator = JWTValidator(secret=secret)
        ctx = validator.validate(token)
        assert ctx is not None
        assert ctx.authenticated is True
        assert ctx.client_id == "claude-desktop"
        assert ctx.auth_type == "jwt"
        assert "mcp:read" in ctx.scopes

    def test_expired_jwt(self):
        secret = "test-secret-key-1234567890123456"
        token = create_jwt_token(
            secret=secret,
            client_id="expired-client",
            expires_in_seconds=-10,  # Already expired
        )
        validator = JWTValidator(secret=secret)
        ctx = validator.validate(token)
        assert ctx is not None
        assert ctx.authenticated is False
        assert "expired" in ctx.error_message.lower()

    def test_invalid_signature_jwt(self):
        secret1 = "test-secret-key-1234567890123456"
        secret2 = "diff-secret-key-1234567890123456"
        token = create_jwt_token(secret=secret1, client_id="test")
        validator = JWTValidator(secret=secret2)
        ctx = validator.validate(token)
        assert ctx is not None
        assert ctx.authenticated is False
        assert "invalid" in ctx.error_message.lower()


class TestAuthManager:
    def test_disabled_auth_allows_all(self):
        mgr = AuthManager(enabled=False)
        ctx = mgr.authenticate(Headers(), QueryParams())
        assert ctx.authenticated is True
        assert ctx.auth_type == "none"

    def test_auth_via_bearer_header(self):
        mgr = AuthManager(api_keys=["test-key-abc"], enabled=True)
        headers = Headers({"authorization": "Bearer test-key-abc"})
        ctx = mgr.authenticate(headers, QueryParams())
        assert ctx.authenticated is True
        assert ctx.auth_type == "api_key"

    def test_auth_via_x_api_key_header(self):
        mgr = AuthManager(api_keys=["test-key-abc"], enabled=True)
        headers = Headers({"x-api-key": "test-key-abc"})
        ctx = mgr.authenticate(headers, QueryParams())
        assert ctx.authenticated is True
        assert ctx.auth_type == "api_key"

    def test_auth_via_query_param(self):
        mgr = AuthManager(api_keys=["test-key-abc"], enabled=True)
        query = QueryParams("token=test-key-abc")
        ctx = mgr.authenticate(Headers(), query)
        assert ctx.authenticated is True
        assert ctx.auth_type == "api_key"

    def test_auth_missing_credentials(self):
        mgr = AuthManager(api_keys=["test-key-abc"], enabled=True)
        ctx = mgr.authenticate(Headers(), QueryParams())
        assert ctx.authenticated is False
        assert "missing" in ctx.error_message.lower()

    def test_auth_invalid_key(self):
        mgr = AuthManager(api_keys=["test-key-abc"], enabled=True)
        headers = Headers({"authorization": "Bearer wrong-key"})
        ctx = mgr.authenticate(headers, QueryParams())
        assert ctx.authenticated is False
        assert "invalid" in ctx.error_message.lower()
