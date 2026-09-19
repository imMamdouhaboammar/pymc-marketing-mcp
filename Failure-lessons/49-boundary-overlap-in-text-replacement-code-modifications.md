# Lesson 49: Boundary Overlap in Text-Replacement Code Modifications

### Context
Automated source-file editing tools (`replace_file_content`) operating on Python abstract syntax tree (AST) code in `src/marketing_mcp/domain/portfolio/contracts.py`.

### What happened
During the remediation of Cubic review feedback on `PortfolioEffectEdge`, a tool call targeted lines 95–102 of `src/marketing_mcp/domain/portfolio/contracts.py`. The replacement text aimed to add the validation for `self.confidence is None`, but the specified `TargetContent` overlapped with the `raise ValueError(` statement inside the preceding `else:` block:
```python
        else:
            if self.source_entity_id == self.target_entity_id:
                raise ValueError(
                    f"Cross-entity effect '{self.effect_type}' requires source_entity_id must not equal target_entity_id, "
...
```
Because the replacement matched from `raise ValueError(` downwards, it truncated the statement, producing broken syntax:
```python
        else:
            if self.source_entity_id == self.target_entity_id:
                raise ValueError(
        if self.confidence is None and self.confidence_provenance != "unspecified":
```

### Observable symptom
Syntactic corruption of the source file. The line following `raise ValueError(` was an unindented `if` block, which would cause an immediate `SyntaxError: unexpected indent` or `SyntaxError: invalid syntax` upon parsing.

### Impact
If left undetected before running tests or committing, this breaks the entire CI build, breaks static analysis (Ruff/Pyright), and halts autonomous agent workflows.

### Incorrect assumption
Assumed that line numbers and target text provided to `replace_file_content` aligned with a complete semantic block boundary, without re-reading the exact enclosing syntax before emitting the edit.

### Root cause
**Confirmed**. The edit boundary started inside a multi-line function call (`raise ValueError(...)`) rather than at an outer statement boundary (`if` or `else:`).

### Why the architecture allowed it
String-matching tools operate on raw text rather than AST nodes. When modifying adjacent blocks of conditional logic, partial statement selection results in syntax truncation.

### Fix
1. Followed the pre-commit inspection invariant: immediately viewed the file around the edit location (`view_file`).
2. Caught the truncated `raise ValueError(` statement before running tests or committing.
3. Restored the full `raise ValueError(f"Cross-entity effect ...")` block and cleanly appended the new validation logic.
4. Ran `uv run ruff check` and `uv run pyright` to mathematically prove 0 syntax or type errors before proceeding.

### Verification
`uv run ruff check src tests scripts` and `uv run pyright` reported clean passes with 0 errors and 0 warnings.

### Prevention rule
> **Every text-replacement tool invocation must anchor its replacement boundaries to complete AST statements (full `if/else`, full function call). Immediately inspect the edited lines with `view_file` and run the compiler/linter before committing.**

### Related code
- `src/marketing_mcp/domain/portfolio/contracts.py`

### Related tests
- `tests/unit/test_portfolio_graph.py`

### Related lessons
- [18-silent-sqlite-cleanup-syntax-error.md](./18-silent-sqlite-cleanup-syntax-error.md)
- [34-dockerfile-posix-sh-process-substitution-syntax-error.md](./34-dockerfile-posix-sh-process-substitution-syntax-error.md)

### Status
Resolved
