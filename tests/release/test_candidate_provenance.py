"""Release workflow provenance and same-byte promotion policy."""

from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"
)


def test_release_checkout_is_bound_to_the_requested_candidate() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "TARGET_TAG:" in workflow
    assert '[[ "${TARGET_TAG}" =~ ^v[0-9]+\\.[0-9]+\\.[0-9]+([-.][0-9A-Za-z.-]+)?$ ]]' in workflow
    assert "ref: ${{ env.TARGET_TAG }}" in workflow
    assert 'git rev-parse "${TARGET_TAG}^{commit}"' in workflow
    assert 'CANDIDATE_SHA=$(git rev-parse HEAD)' in workflow
    assert 'test "${TAG_SHA}" = "${CANDIDATE_SHA}"' in workflow
    assert 'test "${TARGET_TAG}" = "v${APP_VERSION}"' in workflow


def test_release_builds_once_and_smokes_every_exact_artifact() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert workflow.count("uv build") == 1
    assert "--skip-build" in workflow
    assert "dist/*.whl" in workflow
    assert "dist/*.tar.gz" in workflow
    assert "docker run" in workflow
    assert "sha256sum dist/* > dist/SHA256SUMS" in workflow
    assert "sha256sum -c SHA256SUMS" in workflow
    assert workflow.index("uv build") < workflow.index("sha256sum -c SHA256SUMS")


def test_publication_is_explicit_and_cannot_rebuild_or_publish_historical_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "publish:" in workflow
    assert "default: false" in workflow
    assert "if: ${{ github.event_name == 'workflow_dispatch' && inputs.publish }}" in workflow
    publish_step = workflow[workflow.index("- name: Publish verified artifacts") :]
    assert "uv build" not in publish_step
    assert "collect_release_evidence.py" not in publish_step
    assert "docs/release-evidence/*." not in publish_step
    assert "dist/*" in publish_step
