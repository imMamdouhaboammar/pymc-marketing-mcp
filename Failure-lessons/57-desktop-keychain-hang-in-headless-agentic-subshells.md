# Lesson 57: Desktop GUI Keychain Blocks in Headless/Agentic CI Subshells

### Context
Autonomous background agent tasks and non-interactive subshells executing `git push` or remote authenticated Git operations against GitHub repositories.

### What happened
During an autonomous multi-step maintenance loop, background subshell commands running `git push origin <branch>` hung indefinitely without producing any stdout/stderr output or returning an exit code. The process consumed 0% CPU and stayed alive until manually killed.

### Observable symptom
```text
Task: run_command("git push origin ...")
Status: RUNNING (for >300s, no output, 0 CPU activity)
```
Inspecting process stacks revealed the subshell blocked inside macOS system calls waiting on standard I/O for `git-credential-osxkeychain`.

### Impact
Automated release workflows, branch finalization scripts, and autonomous agent loops deadlocked permanently, preventing development branches from landing and blocking CI orchestration.

### Incorrect assumption
Assumed that global macOS git configuration (`credential.helper = osxkeychain`) behaves identically across interactive terminal sessions (where Keychain GUI unlock dialogs pop up) and non-interactive/background agent subshells.

### Root cause
**Confirmed**. The global git credential helper `osxkeychain` requires a connected interactive graphical WindowServer session to prompt for user keychain access. When invoked inside a detached background subprocess, daemon, SSH session, or automated agent tool without an interactive TTY, it attempts to read from stdin or wait on Mach IPC notifications, blocking indefinitely.

### Why the architecture allowed it
The local repository git configuration did not define its own credential helper, implicitly inheriting the system-wide and global `~/.gitconfig` desktop settings.

### Fix
Configured repository-scoped, token-based credential delegation using the GitHub CLI credential helper:
```bash
git config --local credential.helper ""
git config --local --add credential.helper "!gh auth git-credential"
```
This bypasses macOS desktop Keychain GUI prompts and allows Git to retrieve authentication tokens directly from `gh` in a non-interactive, headless subshell.

### Verification
1. Executed `git push origin main` in background agent task.
2. Push completed in 1.8 seconds with exit code 0 and full status output.
3. Subsequent automated PR merges and branch pushes succeeded without human interaction.

### Prevention rule
> **Automated agents and headless CI environments must configure token-based, non-interactive credential helpers locally (`!gh auth git-credential`) and clear desktop GUI credential helpers (`osxkeychain`, `wincred`).**

### Reusable lesson
Any tool that relies on desktop OS keyring services (macOS Keychain, Windows Credential Manager, GNOME Keyring) will hang silently when invoked in non-interactive subshells, Docker containers, or background agent runtimes. Always verify non-interactive fallback behavior or provide explicit environment credentials (`GITHUB_TOKEN`, `gh auth`).

### Related code
- `.git/config`
- `sync_upstream.sh`
- `scripts/fast_deploy.sh`

### Related tests
- `tests/release/test_candidate_provenance.py`

### Status
Resolved
