#!/usr/bin/env python3
"""
PyMC MCP Repository Failure Lesson Scaffolder
Automates the creation, indexing, and state-synchronization of durable failure lessons.

Usage:
    python3 scaffold_lesson.py --slug <kebab-case-slug> --title <Title> --failure-class <Class> --system <System> [options]

Example:
    python3 scaffold_lesson.py \
        --slug "async-job-cancellation-timeout" \
        --title "Async Job Cancellation Timeout in Compute Worker" \
        --failure-class "Async Lifecycle / Fencing" \
        --system "Worker Engine" \
        --rule "Cancelled jobs must immediately drop lease and discard worker completion" \
        --status "Resolved"
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple


SCHEMA_TEMPLATE = """# Lesson {number}: {title}

### Context
{context}

### What happened
{what_happened}

### Why it mattered / Impact
{impact}

### Observable symptom
{symptom}

### Incorrect assumption
{assumption}

### Root cause
{root_cause}

### Why the system allowed it
{architectural_gap}

### Fix
{fix}

### Verification
{verification}

### Prevention rule
> **{rule}**

### Reusable lesson
{reusable_lesson}

### Related code
- `{related_code}`

### Related tests
- `{related_tests}`

### Related lessons
- {related_lessons}

### Status
{status}
"""


def find_repo_root(start_path: Optional[Path] = None) -> Path:
    """Finds the root of the pymc-unified-platform-spec repository."""
    current = (start_path or Path(__file__)).resolve()
    for parent in [current] + list(current.parents):
        if (parent / "state.toon").exists() and (parent / "Failure-lessons").is_dir():
            return parent
    # Fallback to current working directory
    cwd = Path.cwd()
    if (cwd / "state.toon").exists() and (cwd / "Failure-lessons").is_dir():
        return cwd
    raise RuntimeError("Could not determine repository root containing 'state.toon' and 'Failure-lessons/'")


def get_next_lesson_number(failure_lessons_dir: Path) -> int:
    """Scans Failure-lessons directory and returns the next sequential lesson number."""
    max_num = 0
    pattern = re.compile(r"^(\d+)-.*\.md$")
    for item in failure_lessons_dir.iterdir():
        if item.is_file():
            match = pattern.match(item.name)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
    return max_num + 1


def format_lesson_number(num: int) -> str:
    """Formats lesson number with leading zero if less than 10."""
    return f"{num:02d}" if num < 10 else str(num)


def update_lessons_index(
    index_path: Path,
    number: int,
    title: str,
    failure_class: str,
    prevention_rule: str,
    doc_filename: str,
) -> bool:
    """Appends a new lesson entry to Failure-lessons/lessons-index.md table."""
    if not index_path.exists():
        return False

    content = index_path.read_text(encoding="utf-8")
    table_row = f"| Lesson {number} | {failure_class} | {prevention_rule} | [{doc_filename}](./{doc_filename}) |\n"

    # Avoid duplicate entry
    if f"[{doc_filename}](./{doc_filename})" in content:
        return False

    # Check if table ends with a row or newline
    if not content.endswith("\n"):
        content += "\n"
    content += table_row

    index_path.write_text(content, encoding="utf-8")
    return True


def update_state_toon_count(state_toon_path: Path, new_count: int) -> bool:
    """Safely updates failure_lessons_count in state.toon."""
    if not state_toon_path.exists():
        return False

    content = state_toon_path.read_text(encoding="utf-8")
    updated_content = re.sub(
        r"failure_lessons_count:\s*\d+",
        f"failure_lessons_count: {new_count}",
        content,
    )
    if updated_content != content:
        state_toon_path.write_text(updated_content, encoding="utf-8")
        return True
    return False


def scaffold_lesson(
    repo_root: Path,
    slug: str,
    title: str,
    failure_class: str,
    rule: str,
    context: str = "PyMC Unified Platform / Marketing MCP service boundary.",
    what_happened: str = "[Describe the sequence of events and failure mechanism]",
    impact: str = "[Explain correctness, performance, or operational risk]",
    symptom: str = "[Describe the exact error message, traceback, or abnormal behavior]",
    assumption: str = "[What did the implementation or engineer assume that was false?]",
    root_cause: str = "**Confirmed**. [State root cause and factual evidence]",
    architectural_gap: str = "[Explain why the system or test suites allowed this failure]",
    fix: str = "1. [First architectural fix step]\n2. [Second step]",
    verification: str = "[Reference specific test, command, or adversarial experiment]",
    reusable_lesson: str = "[Where else in the codebase or future work this applies]",
    related_code: str = "packages/contracts/... or apps/gateway/src/...",
    related_tests: str = "tests/...",
    related_lessons: str = "[Link to other Failure-lessons/XX-*.md]",
    status: str = "Resolved",
    dry_run: bool = False,
) -> Tuple[Path, int]:
    """Scaffolds the lesson file, updates the index, and bumps state.toon."""
    failure_lessons_dir = repo_root / "Failure-lessons"
    index_path = failure_lessons_dir / "lessons-index.md"
    state_toon_path = repo_root / "state.toon"

    next_num = get_next_lesson_number(failure_lessons_dir)
    formatted_num = format_lesson_number(next_num)
    filename = f"{formatted_num}-{slug}.md"
    target_file = failure_lessons_dir / filename

    content = SCHEMA_TEMPLATE.format(
        number=next_num,
        title=title,
        context=context,
        what_happened=what_happened,
        impact=impact,
        symptom=symptom,
        assumption=assumption,
        root_cause=root_cause,
        architectural_gap=architectural_gap,
        fix=fix,
        verification=verification,
        rule=rule,
        reusable_lesson=reusable_lesson,
        related_code=related_code,
        related_tests=related_tests,
        related_lessons=related_lessons,
        status=status,
    )

    if dry_run:
        print(f"[DRY-RUN] Next Lesson Number: {next_num}")
        print(f"[DRY-RUN] Would create: {target_file}")
        print(f"[DRY-RUN] Would update: {index_path}")
        print(f"[DRY-RUN] Would update: {state_toon_path} (count -> {next_num})")
        return target_file, next_num

    # Write lesson markdown file
    target_file.write_text(content, encoding="utf-8")
    print(f"Created: {target_file}")

    # Update index
    if update_lessons_index(index_path, next_num, title, failure_class, rule, filename):
        print(f"Updated index: {index_path}")
    else:
        print(f"Notice: index already contained {filename} or could not be updated")

    # Update state.toon
    if update_state_toon_count(state_toon_path, next_num):
        print(f"Updated state.toon: failure_lessons_count -> {next_num}")
    else:
        print("Notice: state.toon count unchanged or not found")

    return target_file, next_num


def main():
    parser = argparse.ArgumentParser(description="Scaffold a new failure lesson in PyMC Unified Platform")
    parser.add_argument("--slug", required=True, help="Kebab-case slug for the filename (e.g. async-job-cancellation-timeout)")
    parser.add_argument("--title", required=True, help="Descriptive title for the lesson")
    parser.add_argument("--failure-class", required=True, help="High-level failure category (e.g. Async / State Machine)")
    parser.add_argument("--rule", required=True, help="Binding prevention invariant rule")
    parser.add_argument("--repo-root", default=None, help="Explicit repository root path")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing files")
    parser.add_argument("--context", default=None, help="Context where problem appeared")
    parser.add_argument("--status", default="Resolved", choices=["Resolved", "Partially mitigated", "Unresolved", "Superseded"])

    args = parser.parse_args()

    # Clean slug
    clean_slug = re.sub(r"[^a-zA-Z0-9\-]", "-", args.slug).strip("-").lower()
    clean_slug = re.sub(r"-+", "-", clean_slug)

    root = Path(args.repo_root) if args.repo_root else find_repo_root()

    kwargs = {
        "repo_root": root,
        "slug": clean_slug,
        "title": args.title,
        "failure_class": args.failure_class,
        "rule": args.rule,
        "status": args.status,
        "dry_run": args.dry_run,
    }
    if args.context:
        kwargs["context"] = args.context

    scaffold_lesson(**kwargs)


if __name__ == "__main__":
    main()
