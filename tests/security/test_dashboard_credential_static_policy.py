"""Static security policy tests forbidding insecure browser key generation and storage."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_SRC = REPO_ROOT / "dashboard" / "src"

FORBIDDEN_PATTERNS = (
    # Insecure browser-side key generation
    re.compile(r"function\s+generateRandomKey|const\s+generateRandomKey\s*="),
    # Plaintext / reversible secret storage in Firestore
    re.compile(r"keyHash:\s*fullSecret"),
    re.compile(r"addDoc\(collection\(\w+,\s*['\"]api_keys['\"]\),\s*\{[^}]*keyHash"),
    # Direct raw key storage in localStorage
    re.compile(r"localStorage\.setItem\([`'\"]keys_"),
)


def test_no_insecure_browser_key_generation_or_storage():
    """Verify that dashboard source code contains zero unsafe key generation/storage patterns."""
    assert DASHBOARD_SRC.exists(), "dashboard/src directory must exist"

    violations: list[str] = []
    for path in DASHBOARD_SRC.rglob("*"):
        if not path.is_file() or path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        # Exclude tests or archive
        if "test" in path.name.lower() or "archive" in path.parts:
            continue

        content = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append(
                    f"{path.relative_to(REPO_ROOT)} matches forbidden pattern {pattern.pattern!r}: {match.group(0)}"
                )

    assert not violations, "Insecure dashboard key management patterns found:\n" + "\n".join(violations)
