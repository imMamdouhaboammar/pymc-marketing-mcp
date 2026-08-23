"""Tests for the generated capability document.

Slice 2.3 contract: ``docs/CAPABILITIES.md`` must be generated from the capability registry, and
``scripts/generate_capability_inventory.py --check`` must fail when the committed document no
longer matches the registry.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from marketing_mcp.capabilities import get_capability_inventory, render_capability_markdown

REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "scripts" / "generate_capability_inventory.py"
CAPABILITIES_DOC = REPO_ROOT / "docs" / "CAPABILITIES.md"


def test_rendered_document_lists_every_capability():
    rendered = render_capability_markdown(get_capability_inventory())
    for capability in get_capability_inventory():
        assert capability.name in rendered


def test_rendered_document_marks_generated_origin():
    rendered = render_capability_markdown(get_capability_inventory())
    first_lines = "\n".join(rendered.splitlines()[:6])
    assert "generated" in first_lines.lower()
    assert "src/marketing_mcp/capabilities.py" in rendered


def test_rendered_document_states_status_and_evidence_per_capability():
    rendered = render_capability_markdown(get_capability_inventory())
    assert "| status |" in rendered.lower() or "Status" in rendered
    for capability in get_capability_inventory():
        if capability.status == "experimental":
            continue
        for test_id in capability.evidence_test_ids:
            assert test_id in rendered


def test_committed_document_matches_the_registry():
    assert CAPABILITIES_DOC.exists(), f"{CAPABILITIES_DOC} has not been generated"
    expected = render_capability_markdown(get_capability_inventory())
    assert CAPABILITIES_DOC.read_text(encoding="utf-8") == expected, (
        "docs/CAPABILITIES.md is stale; run "
        "`uv run python scripts/generate_capability_inventory.py`"
    )


def test_generator_check_mode_passes_for_the_committed_document():
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_generator_check_mode_fails_on_drift(tmp_path):
    stale = tmp_path / "CAPABILITIES.md"
    stale.write_text("# Capabilities\n\nstale content\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check", "--output", str(stale)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "drift" in (result.stdout + result.stderr).lower()


def test_generator_writes_the_document(tmp_path):
    target = tmp_path / "CAPABILITIES.md"
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--output", str(target)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert target.read_text(encoding="utf-8") == render_capability_markdown(
        get_capability_inventory()
    )
