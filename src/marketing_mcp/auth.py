from __future__ import annotations

import asyncio
import base64
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

import jwt
from starlette.datastructures import Headers, QueryParams
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from marketing_mcp.config import SecurityProfile, Settings
from marketing_mcp.mcp.context import (
    ExecutionContext,
    reset_current_execution_context,
    set_current_execution_context,
)
from marketing_mcp.security.oauth import RemoteJWTVerifier
from marketing_mcp.security.policy import all_scopes
from marketing_mcp.security.principal import Principal


@dataclass
class AuthContext:
    authenticated: bool = False
    client_id: str = "anonymous"
    auth_type: str = "none"  # "api_key" | "jwt" | "none"
    scopes: list[str] = field(default_factory=lambda: ["*"])
    tenant_id: str | None = None
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
    tenant_id: str | None = None,
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
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    return jwt.encode(payload, secret, algorithm="HS256")


class APIKeyValidator:
    def __init__(
        self,
        valid_keys: list[str] | set[str] | None = None,
        credential_service: Any = None,
    ):
        self.valid_keys = {k.strip() for k in (valid_keys or []) if k.strip()}
        self.credential_service = credential_service

    def add_key(self, key: str) -> None:
        if key.strip():
            self.valid_keys.add(key.strip())

    def validate(self, candidate_key: str) -> AuthContext | None:
        if not candidate_key:
            return None
        candidate = candidate_key.strip()

        # 1. Check dynamic credential service (verifiers & revocations in DB)
        if self.credential_service is not None:
            record = self.credential_service.verify(candidate)
            if record is not None:
                return AuthContext(
                    authenticated=True,
                    client_id=record.owner_subject,
                    auth_type="api_key",
                    scopes=list(record.scopes),
                    tenant_id=record.tenant_id,
                )

        # 2. Check static in-memory/bootstrap keys
        if self.valid_keys:
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
                tenant_id=payload.get("tenant_id") or payload.get("tenant"),
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
        credential_service: Any = None,
        bearer_token_verifier: Any = None,
    ):
        self.enabled = enabled
        self.credential_service = credential_service
        self.bearer_token_verifier = bearer_token_verifier
        self.api_key_validator = APIKeyValidator(api_keys, credential_service=credential_service)
        self.jwt_validator = JWTValidator(
            secret=jwt_secret, issuer=jwt_issuer, audience=jwt_audience
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> AuthManager:
        api_keys = list(settings.api_keys)
        if settings.api_key and settings.api_key not in api_keys:
            api_keys.append(settings.api_key)

        bearer_token_verifier = None
        jwt_secret = settings.jwt_secret
        if settings.security_profile is SecurityProfile.HTTP_PRODUCTION_OAUTH:
            bearer_token_verifier = RemoteJWTVerifier(
                issuer=settings.oauth_issuer or "",
                audience=settings.oauth_audience or "",
                required_scopes=settings.oauth_required_scopes,
                jwks_url=settings.oauth_jwks_url,
                algorithms=settings.oauth_algorithms,
                tenant_claim=settings.oauth_tenant_claim,
                require_tenant=settings.oauth_require_tenant,
            )
            jwt_secret = None

        return cls(
            api_keys=api_keys,
            jwt_secret=jwt_secret,
            jwt_issuer=settings.jwt_issuer,
            jwt_audience=settings.jwt_audience,
            enabled=settings.auth_enabled,
            bearer_token_verifier=bearer_token_verifier,
        )

    @classmethod
    def from_env(cls) -> AuthManager:
        return cls.from_settings(Settings.from_env())

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

        # Production bearer tokens are accepted only after trusted remote verification.
        if self.bearer_token_verifier is not None:
            access_token = self.bearer_token_verifier.verify(token)
            if access_token is None or not access_token.subject:
                return AuthContext(
                    authenticated=False,
                    error_message="Invalid OAuth bearer token.",
                )
            claims = access_token.claims or {}
            tenant_claim = self.bearer_token_verifier.tenant_claim
            tenant_id = claims.get(tenant_claim)
            return AuthContext(
                authenticated=True,
                client_id=access_token.subject,
                auth_type="jwt",
                scopes=list(access_token.scopes),
                tenant_id=str(tenant_id) if tenant_id is not None else None,
            )

        # Local/private JWT compatibility path.
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
        self.public_paths = public_paths or {"/health", "/", "/openapi.json", "/.well-known/mcp.json"}

    async def dispatch(self, request: Request, call_next) -> Response:
        # 1. Allow health checks, dashboard static assets, and the exact public endpoints.
        # Matching on file extensions is deliberately avoided: any protected route whose
        # path happens to end in ".json" would otherwise skip authentication.
        path = request.url.path
        if (
            path in self.public_paths
            or path.startswith(("/health/", "/assets/"))
        ):
            return await call_next(request)

        # 2. Allow OPTIONS pre-flight for CORS
        if request.method == "OPTIONS":
            return await call_next(request)

        # 3. If authentication is disabled, establish anonymous execution context
        if not self.auth_manager.enabled:
            auth_ctx = AuthContext(
                authenticated=True,
                client_id="anonymous",
                scopes=list(all_scopes()),
                tenant_id="default",
                auth_type="stdio",
            )
            request.state.auth = auth_ctx
            principal = Principal(
                subject=auth_ctx.client_id,
                auth_type="stdio",
                scopes=all_scopes(),
                tenant_id="default",
            )
            req_id = request.headers.get("x-request-id", secrets.token_hex(8))
            exec_ctx = ExecutionContext(
                principal=principal,
                request_id=req_id,
                transport="http",
            )
            token = set_current_execution_context(exec_ctx)
            try:
                return await call_next(request)
            finally:
                reset_current_execution_context(token)





        # Artifact download links carry their own short-lived signed token so an AI sandbox
        # can fetch them with plain curl. Without credentials the request goes on to the
        # download handler, which refuses it unless that token verifies.
        if path.startswith("/artifacts/") and not self.auth_manager.extract_token(
            request.headers, request.query_params
        ):
            return await call_next(request)

        # 3. Authenticate request
        if self.auth_manager.bearer_token_verifier is not None:
            auth_ctx = await asyncio.to_thread(
                self.auth_manager.authenticate, request.headers, request.query_params
            )
        else:
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
                            ],
                        },
                    },
                },
            )

        # Store auth context in request state for downstream handlers
        request.state.auth = auth_ctx

        auth_type: Any = "oauth" if auth_ctx.auth_type == "jwt" else ("api_key" if auth_ctx.auth_type == "api_key" else "stdio")
        principal_scopes = all_scopes() if "*" in auth_ctx.scopes else frozenset(auth_ctx.scopes)
        principal = Principal(
            subject=auth_ctx.client_id,
            auth_type=auth_type,
            scopes=principal_scopes,
            tenant_id=auth_ctx.tenant_id or "default",
        )
        req_id = request.headers.get("x-request-id", secrets.token_hex(8))
        exec_ctx = ExecutionContext(
            principal=principal,
            request_id=req_id,
            transport="http",
        )
        token = set_current_execution_context(exec_ctx)
        try:
            return await call_next(request)
        finally:
            reset_current_execution_context(token)
