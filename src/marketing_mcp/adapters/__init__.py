from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marketing_mcp.adapters.platform_client import PlatformClient

__all__ = ["PlatformClient"]


def __getattr__(name: str):
    if name == "PlatformClient":
        from marketing_mcp.adapters.platform_client import PlatformClient

        return PlatformClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
