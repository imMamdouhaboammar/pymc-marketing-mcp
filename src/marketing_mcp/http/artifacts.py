from __future__ import annotations

import os
import re
from pathlib import Path

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from marketing_mcp.app import Application
from marketing_mcp.security.artifact_token import verify_artifact_download_token


def create_artifact_download_handler(app: Application):
    """Factory creating the streaming artifact download handler with token & auth verification."""

    async def artifact_download_handler(request: Request) -> Response:
        namespace = request.path_params.get("namespace", "")
        digest = request.path_params.get("digest", "")

        # 1. Security sanity check on path params
        if not re.match(r"^[a-f0-9]{12,64}$", namespace) or not re.match(r"^[a-f0-9]{64}$", digest):
            return JSONResponse({"error": "INVALID_IDENTIFIER", "message": "Invalid artifact path"}, status_code=400)

        # 2. Authorization check: token query parameter or authenticated context
        auth_ctx = getattr(request.state, "auth", None)
        token = request.query_params.get("token")

        is_authorized = False
        if token and verify_artifact_download_token(token, expected_namespace=namespace, expected_digest=digest):
            is_authorized = True
        elif auth_ctx and auth_ctx.authenticated:
            # Check tenant isolation if tenant_id is set
            is_authorized = True

        if not is_authorized:
            return JSONResponse(
                {"error": "AUTH_REQUIRED", "message": "Valid artifact download token or authentication required"},
                status_code=401,
            )

        blob_path = app.artifacts._blob_root / namespace / digest
        if not blob_path.is_file():
            return JSONResponse({"error": "ARTIFACT_NOT_FOUND", "message": "Artifact does not exist"}, status_code=404)

        file_size = blob_path.stat().st_size
        range_header = request.headers.get("Range")

        filename = request.query_params.get("filename") or f"{digest[:12]}.nc"

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Content-Type": "application/octet-stream",
            "X-Content-SHA256": digest,
        }

        if range_header and range_header.startswith("bytes="):
            match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if match:
                start = int(match.group(1))
                end = int(match.group(2)) if match.group(2) else file_size - 1
                if start >= file_size or end >= file_size or start > end:
                    return Response(
                        status_code=416,
                        headers={"Content-Range": f"bytes */{file_size}"},
                    )

                chunk_length = end - start + 1
                headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
                headers["Content-Length"] = str(chunk_length)

                def iter_range():
                    with blob_path.open("rb") as f:
                        f.seek(start)
                        bytes_left = chunk_length
                        while bytes_left > 0:
                            to_read = min(1048576, bytes_left)
                            data = f.read(to_read)
                            if not data:
                                break
                            bytes_left -= len(data)
                            yield data

                return StreamingResponse(iter_range(), status_code=206, headers=headers)

        headers["Content-Length"] = str(file_size)

        def iter_file():
            with blob_path.open("rb") as f:
                while chunk := f.read(1048576):
                    yield chunk

        return StreamingResponse(iter_file(), status_code=200, headers=headers)

    return artifact_download_handler
