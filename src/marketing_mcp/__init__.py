"""Canonical runtime version API for pymc-marketing-mcp.

The installed distribution metadata is the single source of truth for the application version.
No other module may declare an independent release-version literal.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import platform

DISTRIBUTION_NAME = "pymc-marketing-mcp"

#: Reported when the package is imported from a source tree with no installed distribution.
UNKNOWN_VERSION = "0+unknown"

#: Distributions whose versions are part of the statistical/protocol compatibility contract.
RUNTIME_DEPENDENCIES: tuple[str, ...] = (
    "pymc-marketing",
    "pymc",
    "arviz",
    "mcp",
    "pydantic",
    "xarray",
    "numpy",
    "pandas",
    "h5netcdf",
)


def _installed_version(distribution: str) -> str | None:
    """Return the installed version of ``distribution``, or ``None`` when it is absent."""
    try:
        return importlib_metadata.version(distribution)
    except importlib_metadata.PackageNotFoundError:
        return None


def _application_version() -> str:
    return _installed_version(DISTRIBUTION_NAME) or UNKNOWN_VERSION


__version__: str = _application_version()


def version_info() -> dict[str, str | None]:
    """Return the canonical application version plus installed dependency versions.

    Keys use Python module naming (underscores). Absent distributions map to ``None`` so that
    version reporting never fails because an optional dependency is missing.
    """
    info: dict[str, str | None] = {
        "marketing_mcp": _application_version(),
        "python": platform.python_version(),
    }
    for distribution in RUNTIME_DEPENDENCIES:
        info[distribution.replace("-", "_")] = _installed_version(distribution)
    return info


__all__ = [
    "DISTRIBUTION_NAME",
    "RUNTIME_DEPENDENCIES",
    "UNKNOWN_VERSION",
    "__version__",
    "version_info",
]
