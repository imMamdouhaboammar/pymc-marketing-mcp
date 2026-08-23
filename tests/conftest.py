"""Shared pytest fixtures."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TESTS_ROOT.parent


def _node_ids_in_module(module: Path) -> set[str]:
    """Collect pytest node IDs from a test module without importing it."""
    relative = module.relative_to(REPO_ROOT).as_posix()
    tree = ast.parse(module.read_text(encoding="utf-8"))
    node_ids: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith(
            "test"
        ):
            node_ids.add(f"{relative}::{node.name}")
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            for member in node.body:
                if isinstance(
                    member, ast.FunctionDef | ast.AsyncFunctionDef
                ) and member.name.startswith("test"):
                    node_ids.add(f"{relative}::{node.name}::{member.name}")
    return node_ids


@pytest.fixture(scope="session")
def known_test_node_ids() -> set[str]:
    """Every pytest node ID defined under ``tests/``, resolved statically."""
    node_ids: set[str] = set()
    for module in sorted(TESTS_ROOT.rglob("test_*.py")):
        node_ids |= _node_ids_in_module(module)
    return node_ids
