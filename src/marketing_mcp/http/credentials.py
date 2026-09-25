"""Control plane HTTP endpoints for API key issuance and management."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from marketing_mcp.credentials.service import CredentialService
from marketing_mcp.errors import DomainError
from marketing_mcp.security.principal import Principal


class CredentialControlAPI:
    """HTTP endpoints for dashboard credential management."""

    def __init__(self, credential_service: CredentialService, *, auth_enabled: bool = True):
        self.credential_service = credential_service
        self.auth_enabled = auth_enabled

    def _get_request_principal(self, request: Request) -> Principal:
        """Extract authenticated principal from request state or header."""
        if not self.auth_enabled:
            # With authentication off every caller is "anonymous". Keys minted in that
            # mode would stay valid once authentication is switched on, so refuse.
            raise DomainError(
                "AUTH_FORBIDDEN",
                "Credential management requires server authentication to be enabled",
                next_action="Enable MARKETING_MCP_AUTH_ENABLED before issuing API keys",
            )
        auth_ctx = getattr(request.state, "auth", None)
        if not auth_ctx or not auth_ctx.authenticated:
            raise DomainError("AUTH_REQUIRED", "Authentication required to access credential control plane")
        return Principal(
            subject=auth_ctx.client_id,
            auth_type="oauth" if auth_ctx.auth_type == "jwt" else ("api_key" if auth_ctx.auth_type == "api_key" else "stdio"),
            scopes=frozenset(auth_ctx.scopes),
            tenant_id=auth_ctx.tenant_id or "default",
        )

    async def list_credentials(self, request: Request) -> Response:
        """GET /control/credentials - List API keys for caller's tenant and subject."""
        try:
            principal = self._get_request_principal(request)
            records = self.credential_service.list_for_owner(
                tenant_id=principal.tenant_id or "default",
                owner_subject=principal.subject,
            )
            return JSONResponse({"credentials": [r.to_public_dict() for r in records]})
        except DomainError as e:
            return JSONResponse(e.to_dict(), status_code=401 if e.code == "AUTH_REQUIRED" else 403)

    async def create_credential(self, request: Request) -> Response:
        """POST /control/credentials - Issue a new API key (secret returned ONCE)."""
        try:
            principal = self._get_request_principal(request)
            body = await request.json()
            name = str(body.get("name", "Dashboard Key")).strip() or "Dashboard Key"
            requested_scopes = body.get("scopes", ["marketing:read", "marketing:model", "marketing:decide"])

            issued = self.credential_service.issue(
                tenant_id=principal.tenant_id or "default",
                owner_subject=principal.subject,
                name=name,
                scopes=requested_scopes,
                actor_principal=principal,
            )
            return JSONResponse(
                {
                    "credential": issued.record.to_public_dict(),
                    "secret": issued.secret,
                },
                status_code=201,
            )
        except DomainError as e:
            status_code = 401 if e.code == "AUTH_REQUIRED" else (403 if e.code == "AUTH_FORBIDDEN" else 400)
            return JSONResponse(e.to_dict(), status_code=status_code)

    async def revoke_credential(self, request: Request) -> Response:
        """DELETE /control/credentials/{credential_id} - Revoke an API key."""
        try:
            principal = self._get_request_principal(request)
            credential_id = request.path_params.get("credential_id", "")
            if not credential_id:
                return JSONResponse({"error": {"code": "INPUT_INVALID", "message": "Missing credential_id"}}, status_code=400)

            revoked = self.credential_service.revoke(credential_id, principal)
            return JSONResponse({"credential": revoked.to_public_dict()})
        except DomainError as e:
            status_code = 401 if e.code == "AUTH_REQUIRED" else (404 if e.code == "CREDENTIAL_NOT_FOUND" else 403)
            return JSONResponse(e.to_dict(), status_code=status_code)

    def routes(self) -> list[Route]:
        return [
            Route("/control/credentials", self.list_credentials, methods=["GET"]),
            Route("/control/credentials", self.create_credential, methods=["POST"]),
            Route("/control/credentials/{credential_id}", self.revoke_credential, methods=["DELETE"]),
        ]


__all__ = ["CredentialControlAPI"]
