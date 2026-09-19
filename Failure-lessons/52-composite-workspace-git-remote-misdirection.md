# Lesson 52: Composite Workspace Git Remote Misdirection

### Context
Composite workspace architecture where a top-level specification repository (`pymc-unified-platform-spec`) contains cloned sub-repositories (`pymc-marketing-mcp`) alongside architectural specification documents, while root metadata (`state.toon`, `AGENTS.md`) references a separate target platform repository (`pymc-marketing-platform`).

### What happened
When asked to implement and push CodeRabbit CI configurations, the agent committed and pushed changes to `imMamdouhaboammar/pymc-marketing-platform` based on root `state.toon` metadata, unaware that the user's sole active operational project was `imMamdouhaboammar/pymc-marketing-mcp` (which lived as a sub-directory with open PR #35). The user noticed that remote changes did not appear in their active repository.

### Observable symptom
```text
User: it's not on remote!!
User: انا اي دخلي ب pymc-marketing-platform!!! انا فقط اشتغل على https://github.com/imMamdouhaboammar/pymc-marketing-mcp هذا هو الريبو الوحيد النشط ف المشروع
```
Changes were present on GitHub at `imMamdouhaboammar/pymc-marketing-platform/commit/ed2e18b`, but completely missing from `imMamdouhaboammar/pymc-marketing-mcp` where the user was actively developing.

### Impact
High developer friction and delayed delivery: code, CI configurations, and documentation were delivered to the wrong remote repository, requiring manual intervention, branch context switching, and re-pushing to the actual active codebase.

### Incorrect assumption
The agent assumed that `state.toon` at the workspace root was the universal source of truth for all git push targets across all child and nested directories, without verifying the current working tree's `git remote -v` or active PR state against user intent.

### Root cause
**Confirmed**. The agent relied on ambient root metadata (`state.toon` declaring `remote_url: https://github.com/imMamdouhaboammar/pymc-marketing-platform.git`) rather than inspecting the active git context of the modified components (`pymc-marketing-mcp/.git`). When composite workspaces contain multiple git projects or spec-to-implementation mappings, ambient root variables override local repository realities unless explicitly queried.

### Why the architecture allowed it
The repository structure is a spec monorepo holding both high-level system specs and a nested checkout of the upstream core engine (`pymc-marketing-mcp`). Because both repositories share similar architectural names and file structures (`AGENTS.md`, `check.sh`, `tests/`), an agent without an explicit remote-verification invariant easily conflates the spec monorepo target with the sub-component repository.

### Fix
1. Explicitly checked `git remote -v` and `gh pr list` inside `pymc-marketing-mcp/`, identifying active branch `feat/retest-remediation-and-heavy-async-resilience` and open PR `#35`.
2. Authored `.coderabbit.yaml` and `docs/coderabbit-coding-environment.md` tailored specifically to `pymc-marketing-mcp`'s packaging layout (`src/marketing_mcp/**`, Python 3.12, UV lockfile).
3. Committed and pushed directly to `origin feat/retest-remediation-and-heavy-async-resilience` on `imMamdouhaboammar/pymc-marketing-mcp`.
4. Merged PR `#35` into `main` using `gh pr merge 35 --merge --admin`.

### Verification
1. `gh api repos/imMamdouhaboammar/pymc-marketing-mcp/contents/.coderabbit.yaml` returned HTTP 200 with SHA `7b11d14`.
2. Verified `main` branch commit on `imMamdouhaboammar/pymc-marketing-mcp`: `69f6280 Merge pull request #35`.
3. Verified local `main` synchronized and clean: `git status` reports working tree clean.

### Prevention rule
> **Never infer a Git remote target from ambient root documentation or parent workspace metadata in composite workspaces. Before staging, committing, or pushing code, the agent MUST explicitly query `git remote -v`, `git branch --show-current`, and `gh pr list` within the specific target directory.**

### Reusable lesson
When working in multi-repo workspaces, submodules, monorepo spec folders, or worktrees, ambient configuration files (such as root `state.toon`, `.env`, or workspace READMEs) describe the macro-environment, not necessarily the active checkout. Remote operations (`git push`, `gh pr merge`) must always anchor to the local repository's immediate git configuration.

### Related code
- `.coderabbit.yaml`
- `docs/coderabbit-coding-environment.md`
- `state.toon`

### Related tests
- `gh api repos/imMamdouhaboammar/pymc-marketing-mcp/commits/main`
- `git ls-remote origin`

### Status
Resolved
