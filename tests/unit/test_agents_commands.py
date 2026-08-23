"""Guard that AGENTS.md documents test commands that actually behave as claimed.

Baseline defect B5: AGENTS.md claimed bare ``uv run pytest`` skips the statistical marker (it does
not) and documented ``-m mcp`` (which selects zero tests). These tests make such claims fail.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DOC = REPO_ROOT / "AGENTS.md"

_COMMAND_BLOCK = re.compile(r"```bash\n(?P<body>.*?)```", re.DOTALL)
# Match -m <expr>, where <expr> is either a quoted expression or a single bare token.
_MARKER = re.compile(r"-m\s+(?:\"(?P<quoted>[^\"]+)\"|'(?P<squoted>[^']+)'|(?P<bare>[A-Za-z0-9_]+))")


def _agents_command_block() -> str:
    match = _COMMAND_BLOCK.search(AGENTS_DOC.read_text(encoding="utf-8"))
    assert match, "AGENTS.md has no ```bash command block"
    return match.group("body")


def _documented_marker_expressions() -> list[str]:
    block = _agents_command_block()
    expressions: list[str] = []
    for match in _MARKER.finditer(block):
        expressions.append(match.group("quoted") or match.group("squoted") or match.group("bare"))
    return expressions


def _collected_count(marker_expression: str) -> int:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-m", marker_expression],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if "no tests collected" in output or "no tests ran" in output:
        return 0
    match = re.search(r"(\d+)(?:/\d+)?\s+tests? (?:collected|selected)", output)
    return int(match.group(1)) if match else 0


def test_agents_documents_at_least_one_marker_command():
    assert _documented_marker_expressions(), "AGENTS.md documents no `-m` marker commands"


@pytest.mark.parametrize("expression", _documented_marker_expressions())
def test_every_documented_marker_selects_tests(expression):
    assert _collected_count(expression) > 0, (
        f"AGENTS.md documents `-m {expression}` but it selects no tests"
    )


def test_agents_does_not_claim_bare_pytest_skips_statistical():
    """Bare ``uv run pytest`` runs everything; the doc must not claim otherwise."""
    block = _agents_command_block()
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        command, _, comment = stripped.partition("#")
        if command.strip() == "uv run pytest":
            lowered = comment.lower()
            claims_exclusion = "skip" in lowered or "exclud" in lowered or "not statistical" in lowered
            assert not claims_exclusion, (
                "AGENTS.md claims bare `uv run pytest` skips statistical tests, but it runs them"
            )


def test_agents_documents_the_fast_test_command():
    block = _agents_command_block()
    assert "not statistical" in block, (
        "AGENTS.md should document `uv run pytest -m \"not statistical\"` as the fast command"
    )
