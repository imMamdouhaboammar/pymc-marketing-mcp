"""Policy regression test for profile-summary-card automation."""

import re
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).parents[2] / ".github/workflows/profile_summary_cards.yml"


def test_profile_cards_cannot_write_to_or_loop_on_product_branch() -> None:
    if not WORKFLOW.exists():
        pytest.skip("profile_summary_cards.yml workflow is not present in .github/workflows")
    workflow = WORKFLOW.read_text(encoding="utf-8")

    trigger_block = workflow.split("permissions:", 1)[0]
    assert "schedule:" in trigger_block
    assert "workflow_dispatch:" in trigger_block
    assert not re.search(r"^  push:\s*$", trigger_block, re.MULTILINE)

    assert re.search(r"^permissions:\s*\n  contents: read\s*$", workflow, re.MULTILINE)
    assert re.search(
        r"^  build:\s*\n(?:.*\n)*?    permissions:\s*\n      contents: write\s*$",
        workflow,
        re.MULTILINE,
    )
    assert "BRANCH_NAME: profile-summary-cards" in workflow
    assert "refs/heads/main" not in workflow
    assert not re.search(r"BRANCH_NAME:\s*main\s*$", workflow, re.MULTILINE)
