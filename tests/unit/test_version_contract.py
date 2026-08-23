"""Contract tests for the canonical runtime version API.

Slice 1.1 contract: ``marketing_mcp.__version__`` must be derived from installed distribution
metadata rather than an independently maintained literal, and ``marketing_mcp.version_info()`` must
report the application version alongside the installed statistical/protocol dependency versions.
"""

from __future__ import annotations

import importlib.metadata as importlib_metadata
import re
import sys
import tomllib
from pathlib import Path

import pytest

import marketing_mcp

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_INIT = REPO_ROOT / "src" / "marketing_mcp" / "__init__.py"

# A literal release version assignment, e.g. ``__version__ = "0.4.0"``.
HARDCODED_VERSION_ASSIGNMENT = re.compile(r"""__version__\s*(:[^=]+)?=\s*["']\d+\.\d+""")


def test_runtime_version_is_not_a_hardcoded_literal():
    """The package must not carry its own release-version literal."""
    source = PACKAGE_INIT.read_text(encoding="utf-8")
    match = HARDCODED_VERSION_ASSIGNMENT.search(source)
    assert match is None, (
        f"{PACKAGE_INIT} assigns a hardcoded release version ({match.group(0)!r} if matched); "
        "derive __version__ from distribution metadata instead"
    )


def test_runtime_version_matches_distribution_and_pyproject():
    """Drift guard: runtime, installed distribution, and pyproject versions must agree."""
    installed = importlib_metadata.version("pymc-marketing-mcp")
    declared = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert marketing_mcp.__version__ == installed
    assert marketing_mcp.__version__ == declared["project"]["version"]


def test_version_info_reports_application_version():
    info = marketing_mcp.version_info()
    assert info["marketing_mcp"] == marketing_mcp.__version__


def test_version_info_reports_installed_pymc_marketing_version():
    info = marketing_mcp.version_info()
    assert info["pymc_marketing"] == importlib_metadata.version("pymc-marketing")


def test_version_info_covers_statistical_and_protocol_boundary():
    info = marketing_mcp.version_info()
    for dependency in ("pymc_marketing", "pymc", "arviz", "mcp", "pydantic", "xarray"):
        assert info[dependency] is not None, f"{dependency} version missing from version_info()"


def test_version_info_reports_none_for_missing_package(monkeypatch):
    """Missing optional packages must not raise; they report None."""
    real_version = importlib_metadata.version

    def fake_version(name: str) -> str:
        if name == "arviz":
            raise importlib_metadata.PackageNotFoundError(name)
        return real_version(name)

    monkeypatch.setattr(marketing_mcp.importlib_metadata, "version", fake_version)
    info = marketing_mcp.version_info()
    assert info["arviz"] is None
    assert info["marketing_mcp"] == marketing_mcp.__version__


def test_version_info_is_json_serializable_and_stable():
    first = marketing_mcp.version_info()
    second = marketing_mcp.version_info()
    assert first == second
    assert all(isinstance(k, str) for k in first)
    assert all(v is None or isinstance(v, str) for v in first.values())


def test_cli_version_flag_reports_canonical_version(monkeypatch, capsys):
    from marketing_mcp.cli import main

    monkeypatch.setattr(sys, "argv", ["marketing-mcp", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 0
    assert marketing_mcp.__version__ in capsys.readouterr().out
