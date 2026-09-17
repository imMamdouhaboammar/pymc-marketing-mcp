"""Safe remote dataset fetching with DNS pinning, SSRF mitigation, and streaming byte caps."""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

from marketing_mcp.errors import DomainError
from marketing_mcp.security.redaction import redact_url


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True if IP is loopback, private, link-local, multicast, or reserved."""
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_destination_host(hostname: str) -> None:
    """Resolve hostname and reject any private, loopback, or cloud-metadata destinations."""
    # Check if host is literally an IP
    try:
        ip = ipaddress.ip_address(hostname)
        if is_ip_blocked(ip):
            raise DomainError(
                "SSRF_DETECTED",
                f"Connection to blocked/private IP {hostname} is prohibited",
                evidence={"host": hostname, "ip": str(ip)},
                next_action="Provide a publicly reachable HTTP/HTTPS URL",
            )
        return
    except ValueError:
        pass

    # Hostname resolution
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise DomainError(
            "UNREACHABLE_SOURCE",
            f"Failed to resolve hostname: {hostname}",
            evidence={"hostname": hostname, "error": str(exc)},
            next_action="Verify that hostname is valid and resolvable",
        ) from exc

    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        ip = ipaddress.ip_address(ip_str)
        if is_ip_blocked(ip):
            raise DomainError(
                "SSRF_DETECTED",
                f"Hostname {hostname} resolved to prohibited private/internal IP {ip_str}",
                evidence={"hostname": hostname, "resolved_ip": ip_str},
                next_action="Provide a publicly reachable HTTP/HTTPS URL",
            )


def safe_fetch_remote_dataset(
    url: str,
    *,
    max_bytes: int = 100 * 1024 * 1024,
    timeout_seconds: float = 30.0,
    max_redirects: int = 5,
) -> tuple[bytes, str]:
    """Safely fetch remote dataset using streaming byte cap and SSRF validation on every hop."""
    current_url = url
    for hop in range(max_redirects + 1):
        parsed = urllib.parse.urlparse(current_url)
        if parsed.scheme not in ("http", "https"):
            raise DomainError(
                "UNSUPPORTED_SCHEME",
                f"URL scheme '{parsed.scheme}' not allowed; must be http or https",
                evidence={"url": current_url},
                next_action="Provide a valid http:// or https:// URL",
            )

        hostname = parsed.hostname
        if not hostname:
            raise DomainError("INPUT_INVALID", "URL is missing hostname", evidence={"url": current_url})

        validate_destination_host(hostname)

        # Custom handler to disallow automatic urllib redirects so we inspect every hop
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def http_error_302(self, req, fp, code, msg, headers):
                return fp
            http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302

        opener = urllib.request.build_opener(NoRedirectHandler)
        req = urllib.request.Request(
            current_url,
            headers={"User-Agent": "PyMC-Marketing-MCP/0.5.0 (Safe Dataset Fetch)"},
        )

        try:
            with opener.open(req, timeout=timeout_seconds) as resp:
                status = getattr(resp, "status", getattr(resp, "code", 200))
                if status in (301, 302, 303, 307, 308):
                    new_loc = resp.headers.get("Location")
                    if not new_loc:
                        raise DomainError("UNREACHABLE_SOURCE", "Redirect response missing Location header")
                    current_url = urllib.parse.urljoin(current_url, new_loc)
                    continue

                if status != 200:
                    raise DomainError(
                        "UNREACHABLE_SOURCE",
                        f"HTTP {status} when downloading dataset from URL",
                        evidence={"status": status, "url": current_url},
                    )

                resp.headers.get("Content-Type", "")
                chunks = []
                total_bytes = 0
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > max_bytes:
                        raise DomainError(
                            "RESOURCE_LIMIT_EXCEEDED",
                            f"Remote dataset exceeded maximum allowed size of {max_bytes} bytes",
                            evidence={"max_bytes": max_bytes, "received_bytes": total_bytes},
                            next_action="Upload a smaller dataset or increase max_dataset_mb",
                        )
                    chunks.append(chunk)

        except urllib.error.HTTPError as exc:
            safe_url = redact_url(current_url)
            raise DomainError(
                "UPSTREAM_HTTP_ERROR",
                f"HTTP {exc.code} error downloading remote dataset: {exc.reason}",
                evidence={"url": safe_url, "status_code": exc.code, "reason": str(exc.reason)},
                next_action="Check remote server status, credentials, and dataset URL",
            ) from exc
        except TimeoutError as exc:
            safe_url = redact_url(current_url)
            raise DomainError(
                "UPSTREAM_TIMEOUT",
                f"Timed out downloading remote dataset after {timeout_seconds}s",
                evidence={"url": safe_url, "timeout_seconds": timeout_seconds},
                next_action="Verify remote network speed or increase timeout",
            ) from exc
        except urllib.error.URLError as exc:
            safe_url = redact_url(current_url)
            if isinstance(exc.reason, socket.timeout) or "timed out" in str(exc.reason).lower():
                raise DomainError(
                    "UPSTREAM_TIMEOUT",
                    f"Timed out downloading remote dataset after {timeout_seconds}s",
                    evidence={"url": safe_url, "timeout_seconds": timeout_seconds},
                    next_action="Verify remote network speed or increase timeout",
                ) from exc
            raise DomainError(
                "UNREACHABLE_SOURCE",
                f"Network error downloading dataset: {exc.reason}",
                evidence={"url": safe_url, "reason": str(exc.reason)},
                next_action="Verify remote host availability and network connection",
            ) from exc

    raise DomainError("RESOURCE_LIMIT_EXCEEDED", "Exceeded maximum allowed redirect hops (5)")
