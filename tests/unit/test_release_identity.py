"""Release packaging identity contract.

Task 5 contract: one application version, one commit identity, image labels that carry both, wheel
metadata that matches the runtime version, deployment scripts that do not invent a default tag, and
a source distribution that ships neither vendored `node_modules` nor secret files.

Baseline defects covered: B3 (`v0.5.0` invented in deploy script and dashboard) and B6 (sdist ships
`dashboard/node_modules`, and in fact `dashboard/.env.local`).
"""

from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

from marketing_mcp import __version__
from marketing_mcp.release_identity import (
    DISTRIBUTION_NAME,
    check_dashboard_version,
    check_deploy_script,
    check_dockerfile_labels,
    check_sdist_members,
    check_wheel_version,
    derive_image_tag,
    verify_release_identity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER = REPO_ROOT / "scripts" / "verify_release_identity.py"
COMMIT = "8f7e2a9a03b4d0d580e43eb21270e917953e0b11"


# --- image tag derivation --------------------------------------------------------------------


def test_derive_image_tag_combines_version_and_commit():
    tag = derive_image_tag(__version__, COMMIT)
    assert tag.startswith(f"{__version__}-g")
    assert COMMIT[:12] in tag


def test_derive_image_tag_is_deterministic():
    assert derive_image_tag(__version__, COMMIT) == derive_image_tag(__version__, COMMIT)


def test_derive_image_tag_rejects_empty_version():
    with pytest.raises(ValueError, match="version"):
        derive_image_tag("", COMMIT)


def test_derive_image_tag_rejects_unknown_version():
    with pytest.raises(ValueError, match="version"):
        derive_image_tag("0+unknown", COMMIT)


def test_derive_image_tag_rejects_short_commit():
    with pytest.raises(ValueError, match="commit"):
        derive_image_tag(__version__, "abc123")


# --- wheel version ---------------------------------------------------------------------------


def test_wheel_version_mismatch_is_flagged():
    problems = check_wheel_version(wheel_version="0.5.0", runtime_version=__version__)
    assert problems
    assert "0.5.0" in problems[0]


def test_wheel_version_match_is_accepted():
    assert check_wheel_version(wheel_version=__version__, runtime_version=__version__) == []


# --- sdist members ---------------------------------------------------------------------------


def test_sdist_members_flag_vendored_node_modules():
    members = [
        "pkg-0.4.0/src/marketing_mcp/__init__.py",
        "pkg-0.4.0/dashboard/node_modules/react/index.js",
    ]
    problems = check_sdist_members(members)
    assert any("node_modules" in p for p in problems)


def test_sdist_members_flag_env_secret_files():
    members = [
        "pkg-0.4.0/src/marketing_mcp/__init__.py",
        "pkg-0.4.0/dashboard/.env.local",
    ]
    problems = check_sdist_members(members)
    assert any(".env" in p for p in problems)


def test_sdist_members_require_the_python_package():
    problems = check_sdist_members(["pkg-0.4.0/README.md"])
    assert any("marketing_mcp" in p for p in problems)


def test_clean_sdist_member_listing_is_accepted():
    members = [
        "pkg-0.4.0/pyproject.toml",
        "pkg-0.4.0/README.md",
        "pkg-0.4.0/src/marketing_mcp/__init__.py",
        "pkg-0.4.0/src/marketing_mcp/cli.py",
    ]
    assert check_sdist_members(members) == []


# --- deploy script ---------------------------------------------------------------------------


def test_deploy_script_with_hardcoded_prerelease_default_is_flagged():
    problems = check_deploy_script('IMAGE_TAG="${IMAGE_TAG:-v0.5.0}"\n')
    assert problems
    assert "v0.5.0" in problems[0]


def test_deploy_script_deriving_tag_from_version_is_accepted():
    text = 'IMAGE_TAG="${IMAGE_TAG:-${APP_VERSION}-g${GIT_SHA}}"\n'
    assert check_deploy_script(text) == []


# --- dockerfile labels -----------------------------------------------------------------------


def test_dockerfile_without_oci_labels_is_flagged():
    problems = check_dockerfile_labels("FROM python:3.12-slim\nCMD [\"marketing-mcp\"]\n")
    assert problems


def test_dockerfile_with_version_and_revision_labels_is_accepted():
    text = (
        "FROM python:3.12-slim\n"
        "ARG APP_VERSION=0.0.0\n"
        "ARG GIT_COMMIT=unknown\n"
        'LABEL org.opencontainers.image.version="${APP_VERSION}" \\\n'
        '      org.opencontainers.image.revision="${GIT_COMMIT}"\n'
    )
    assert check_dockerfile_labels(text) == []


# --- dashboard version -----------------------------------------------------------------------


def test_dashboard_version_drift_is_flagged():
    problems = check_dashboard_version("PyMC Marketing MCP Server • v0.5.0", __version__)
    assert problems
    assert "0.5.0" in problems[0]


def test_dashboard_version_matching_canonical_is_accepted():
    text = f"PyMC Marketing MCP Server • v{__version__}"
    assert check_dashboard_version(text, __version__) == []


# --- repository-wide contract ----------------------------------------------------------------


def test_repository_release_identity_source_is_clean():
    problems = verify_release_identity(
        runtime_version=__version__,
        deploy_script_text=(REPO_ROOT / "scripts" / "deploy_cloud_run.sh").read_text(
            encoding="utf-8"
        ),
        dockerfile_text=(REPO_ROOT / "Dockerfile").read_text(encoding="utf-8"),
        dashboard_text=(REPO_ROOT / "dashboard" / "src" / "App.tsx").read_text(encoding="utf-8"),
    )
    assert problems == [], "release identity drift:\n" + "\n".join(problems)


# --- built artifacts -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_dist(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        ["uv", "build", "--out-dir", str(out)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"uv build unavailable in this environment: {result.stderr[-400:]}")
    return out


def test_built_sdist_excludes_node_modules_and_secrets(built_dist):
    sdist = next(built_dist.glob("*.tar.gz"))
    with tarfile.open(sdist) as tar:
        members = tar.getnames()
    problems = check_sdist_members(members)
    assert problems == [], "sdist contents violate the packaging contract:\n" + "\n".join(problems)


def test_built_sdist_is_small(built_dist):
    sdist = next(built_dist.glob("*.tar.gz"))
    size_mb = sdist.stat().st_size / (1024 * 1024)
    assert size_mb < 2.0, f"sdist is {size_mb:.1f} MB; vendored assets likely leaked back in"


def test_built_wheel_metadata_version_matches_runtime(built_dist):
    wheel = next(built_dist.glob("*.whl"))
    with zipfile.ZipFile(wheel) as zf:
        metadata_name = next(n for n in zf.namelist() if n.endswith(".dist-info/METADATA"))
        metadata = zf.read(metadata_name).decode("utf-8")
    version_line = next(line for line in metadata.splitlines() if line.startswith("Version:"))
    wheel_version = version_line.split(":", 1)[1].strip()
    assert check_wheel_version(wheel_version=wheel_version, runtime_version=__version__) == []
    name_line = next(line for line in metadata.splitlines() if line.startswith("Name:"))
    assert name_line.split(":", 1)[1].strip() == DISTRIBUTION_NAME


def test_verifier_script_passes_on_built_dist(built_dist):
    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist-dir", str(built_dist)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
