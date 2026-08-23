from __future__ import annotations

import base64
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

import jwt
from starlette.datastructures import Headers, QueryParams
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


@dataclass
class AuthContext:
    authenticated: bool = False
    client_id: str = "anonymous"
    auth_type: str = "none"  # "api_key" | "jwt" | "none"
    scopes: list[str] = field(default_factory=lambda: ["*"])
    error_message: str | None = None


def generate_api_key(prefix: str = "mcp_live_") -> str:
    """Generate a high-entropy cryptographically secure API key."""
    random_bytes = secrets.token_bytes(32)
    token = base64.urlsafe_b64encode(random_bytes).decode("ascii").rstrip("=")
    return f"{prefix}{token}"


def create_jwt_token(
    secret: str,
    client_id: str = "ai-client",
    scopes: list[str] | None = None,
    expires_in_seconds: int = 86400 * 30,  # 30 days default
    issuer: str = "pymc-marketing-mcp",
    audience: str = "mcp-clients",
) -> str:
    """Create a signed HS256 JWT bearer token."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": client_id,
        "iat": now,
        "exp": now + expires_in_seconds,
        "iss": issuer,
        "aud": audience,
        "scopes": scopes or ["*"],
    }
    return jwt.encode(payload, secret, algorithm="HS256")


class APIKeyValidator:
    def __init__(self, valid_keys: list[str] | set[str] | None = None):
        self.valid_keys = {k.strip() for k in (valid_keys or []) if k.strip()}

    def add_key(self, key: str) -> None:
        if key.strip():
            self.valid_keys.add(key.strip())

    def validate(self, candidate_key: str) -> AuthContext | None:
        if not candidate_key or not self.valid_keys:
            return None
        candidate = candidate_key.strip()
        matched = False
        for valid_key in self.valid_keys:
            if secrets.compare_digest(candidate, valid_key):
                matched = True
                break
        if matched:
            return AuthContext(
                authenticated=True,
                client_id="api-key-client",
                auth_type="api_key",
                scopes=["*"],
            )
        return None


class JWTValidator:
    def __init__(
        self,
        secret: str | None = None,
        issuer: str = "pymc-marketing-mcp",
        audience: str = "mcp-clients",
    ):
        self.secret = secret
        self.issuer = issuer
        self.audience = audience

    def validate(self, token: str) -> AuthContext | None:
        if not self.secret or not token:
            return None
        try:
            payload = jwt.decode(
                token.strip(),
                self.secret,
                algorithms=["HS256"],
                issuer=self.issuer,
                audience=self.audience,
            )
            return AuthContext(
                authenticated=True,
                client_id=payload.get("sub", "jwt-client"),
                auth_type="jwt",
                scopes=payload.get("scopes", ["*"]),
            )
        except jwt.ExpiredSignatureError:
            return AuthContext(
                authenticated=False,
                error_message="Token has expired",
            )
        except jwt.InvalidTokenError as e:
            return AuthContext(
                authenticated=False,
                error_message=f"Invalid token: {e}",
            )


class AuthManager:
    def __init__(
        self,
        api_keys: list[str] | set[str] | None = None,
        jwt_secret: str | None = None,
        jwt_issuer: str = "pymc-marketing-mcp",
        jwt_audience: str = "mcp-clients",
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.api_key_validator = APIKeyValidator(api_keys)
        self.jwt_validator = JWTValidator(
            secret=jwt_secret, issuer=jwt_issuer, audience=jwt_audience
        )

    @classmethod
    def from_env(cls) -> AuthManager:
        api_key_env = os.getenv("MARKETING_MCP_API_KEY", "").strip()
        api_keys_list = [k.strip() for k in api_key_env.split(",") if k.strip()]
        jwt_secret = os.getenv("MARKETING_MCP_JWT_SECRET", "").strip() or None
        jwt_issuer = os.getenv("MARKETING_MCP_JWT_ISSUER", "pymc-marketing-mcp")
        jwt_audience = os.getenv("MARKETING_MCP_JWT_AUDIENCE", "mcp-clients")

        # Explicit toggle or inferred from presence of keys
        auth_enabled_str = os.getenv("MARKETING_MCP_AUTH_ENABLED", "").strip().lower()
        if auth_enabled_str in ("1", "true", "yes"):
            enabled = True
        elif auth_enabled_str in ("0", "false", "no"):
            enabled = False
        else:
            enabled = bool(api_keys_list or jwt_secret)

        return cls(
            api_keys=api_keys_list,
            jwt_secret=jwt_secret,
            jwt_issuer=jwt_issuer,
            jwt_audience=jwt_audience,
            enabled=enabled,
        )

    def extract_token(self, headers: Headers, query_params: QueryParams) -> str | None:
        """Extract credentials from headers only.

        Query-string credentials are never accepted: URLs are logged by
        proxies and browsers and leak secrets. ``query_params`` is accepted
        for interface compatibility but deliberately ignored.
        """
        # 1. Authorization header: Bearer <token>
        auth_header = headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()
            if token:
                return token

        # 2. X-API-Key header
        x_api_key = headers.get("x-api-key", "").strip()
        if x_api_key:
            return x_api_key

        return None

    def authenticate(self, headers: Headers, query_params: QueryParams) -> AuthContext:
        if not self.enabled:
            return AuthContext(authenticated=True, client_id="anonymous", auth_type="none")

        token = self.extract_token(headers, query_params)
        if not token:
            return AuthContext(
                authenticated=False,
                error_message="Missing authentication credentials. Provide Authorization: Bearer <TOKEN> or X-API-Key header.",
            )

        # Try API Key first
        api_ctx = self.api_key_validator.validate(token)
        if api_ctx and api_ctx.authenticated:
            return api_ctx

        # Try JWT validation
        jwt_ctx = self.jwt_validator.validate(token)
        if jwt_ctx:
            return jwt_ctx

        return AuthContext(
            authenticated=False,
            error_message="Invalid API Key or JWT token signature.",
        )


class MCPAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_manager: AuthManager, public_paths: set[str] | None = None):
        super().__init__(app)
        self.auth_manager = auth_manager
        self.public_paths = public_paths or {"/health", "/", "/openapi.json"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Allow health check, dashboard static assets, and public endpoints without auth
        path = request.url.path
        if (
            path in self.public_paths
            or path.startswith("/assets/")
            or path.endswith((".js", ".css", ".html", ".ico", ".svg", ".png", ".json"))
            or not self.auth_manager.enabled
        ):
            return await call_next(request)



        # 2. Allow OPTIONS pre-flight for CORS
        if request.method == "OPTIONS":
            return await call_next(request)


        # 3. Authenticate request
        auth_ctx = self.auth_manager.authenticate(request.headers, request.query_params)
        if not auth_ctx.authenticated:
            return JSONResponse(
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer realm="pymc-marketing-mcp"'},
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": f"Unauthorized: {auth_ctx.error_message or 'Authentication failed'}",
                        "data": {
                            "status": "unauthorized",
                            "supported_schemes": [
                                "Authorization: Bearer <API_KEY_OR_JWT>",
                                "X-API-Key: <API_KEY>",
                                "URL Query Parameter: ?token=<TOKEN>",
                            ],
                        },
                    },
                },
            )

        # Store auth context in request state for downstream handlers
        request.state.auth = auth_ctx
        return await call_next(request)
