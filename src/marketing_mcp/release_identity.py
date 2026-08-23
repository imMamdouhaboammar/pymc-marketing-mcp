"""Release packaging identity checks.

A release has exactly one application version and one commit identity. Everything that carries a
version — the wheel metadata, the container image labels, the deployment tag, the dashboard footer —
must agree with the canonical runtime version, and the source distribution must ship only the
project, never vendored dependencies or secret files.

The functions here are pure and stdlib-only so they can run in a unit test and in
``scripts/verify_release_identity.py`` without a build environment.
"""

from __future__ import annotations

import re

from marketing_mcp import UNKNOWN_VERSION, __version__

DISTRIBUTION_NAME = "pymc-marketing-mcp"
IMPORT_PACKAGE_PATH = "src/marketing_mcp/__init__.py"

#: Minimum characters of a commit SHA required to form an image tag.
_MIN_COMMIT_LEN = 7
_DEFAULT_SHORT_LEN = 12

#: Files/paths that must never appear in a source distribution.
_FORBIDDEN_SDIST_MARKERS: tuple[str, ...] = (
    "node_modules/",
    "/.env",
    "firebase-debug.log",
    "/dist/",  # built frontend bundles do not belong in the python sdist
    ".venv/",
)

_SEMVER = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")
_DEPLOY_DEFAULT_TAG = re.compile(r"""IMAGE_TAG=["']?\$\{IMAGE_TAG:-(?P<default>[^}"']+)\}""")
_REQUIRED_OCI_LABELS = ("org.opencontainers.image.version", "org.opencontainers.image.revision")


def derive_image_tag(version: str, commit_sha: str, *, short_len: int = _DEFAULT_SHORT_LEN) -> str:
    """Derive a deterministic image tag from the application version and commit SHA.

    Raises:
        ValueError: If ``version`` is empty/unknown or ``commit_sha`` is too short to identify a
            commit.
    """
    if not version or version == UNKNOWN_VERSION:
        raise ValueError(f"cannot derive an image tag from version {version!r}")
    if len(commit_sha) < _MIN_COMMIT_LEN:
        raise ValueError(
            f"commit SHA {commit_sha!r} is too short (need at least {_MIN_COMMIT_LEN} chars)"
        )
    return f"{version}-g{commit_sha[:short_len]}"


def check_wheel_version(*, wheel_version: str, runtime_version: str = __version__) -> list[str]:
    """Flag a wheel whose metadata version disagrees with the runtime version."""
    if wheel_version != runtime_version:
        return [
            (
                f"wheel metadata version {wheel_version!r} does not match runtime version "
                f"{runtime_version!r}"
            )
        ]
    return []


def check_sdist_members(members: list[str]) -> list[str]:
    """Flag forbidden files in a source distribution and require the importable package."""
    problems: list[str] = []
    for name in members:
        for marker in _FORBIDDEN_SDIST_MARKERS:
            if marker in name:
                problems.append(f"sdist ships forbidden path {name!r} (matched {marker!r})")
                break
    if not any("/src/marketing_mcp/__init__.py" in name for name in members):
        problems.append("sdist does not contain src/marketing_mcp/__init__.py")
    return problems


def check_deploy_script(text: str) -> list[str]:
    """Flag a deployment script that defaults IMAGE_TAG to an invented literal version."""
    problems: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = _DEPLOY_DEFAULT_TAG.search(line)
        if not match:
            continue
        default = match.group("default")
        # A derived default (referencing another variable) is fine; a literal version is not.
        if "$" in default:
            continue
        if _SEMVER.search(default):
            problems.append(
                f"line {number}: deployment defaults IMAGE_TAG to invented literal {default!r}; "
                "derive it from the application version and commit or require it explicitly"
            )
    return problems


def check_dockerfile_labels(text: str) -> list[str]:
    """Flag a Dockerfile that omits OCI version/revision labels."""
    problems: list[str] = []
    for label in _REQUIRED_OCI_LABELS:
        if label not in text:
            problems.append(f"Dockerfile is missing required OCI label {label!r}")
    return problems


def check_dashboard_version(text: str, runtime_version: str = __version__) -> list[str]:
    """Flag a dashboard version literal that disagrees with the runtime version."""
    problems: list[str] = []
    for match in _SEMVER.finditer(text):
        version = match.group(1)
        if version != runtime_version:
            problems.append(
                f"dashboard shows version {match.group(0)!r} but the canonical runtime version "
                f"is {runtime_version!r}"
            )
    return problems


def verify_release_identity(
    *,
    runtime_version: str = __version__,
    wheel_version: str | None = None,
    sdist_members: list[str] | None = None,
    deploy_script_text: str | None = None,
    dockerfile_text: str | None = None,
    dashboard_text: str | None = None,
    image_tag: str | None = None,
    commit_sha: str | None = None,
) -> list[str]:
    """Aggregate every packaging-identity check over whichever inputs are supplied."""
    problems: list[str] = []
    if wheel_version is not None:
        problems += check_wheel_version(
            wheel_version=wheel_version, runtime_version=runtime_version
        )
    if sdist_members is not None:
        problems += check_sdist_members(sdist_members)
    if deploy_script_text is not None:
        problems += check_deploy_script(deploy_script_text)
    if dockerfile_text is not None:
        problems += check_dockerfile_labels(dockerfile_text)
    if dashboard_text is not None:
        problems += check_dashboard_version(dashboard_text, runtime_version)
    if image_tag is not None and commit_sha is not None:
        expected = derive_image_tag(runtime_version, commit_sha)
        acceptable = {expected, runtime_version, f"v{runtime_version}", commit_sha, commit_sha[:12]}
        if image_tag not in acceptable:
            problems.append(
                f"image tag {image_tag!r} is not derived from version {runtime_version!r} and "
                f"commit {commit_sha[:12]!r}"
            )
    return problems


__all__ = [
    "DISTRIBUTION_NAME",
    "check_dashboard_version",
    "check_deploy_script",
    "check_dockerfile_labels",
    "check_sdist_members",
    "check_wheel_version",
    "derive_image_tag",
    "verify_release_identity",
]
