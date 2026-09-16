# Failure Lesson 34: Dockerfile POSIX /bin/sh Process Substitution Syntax Error

## Executive Summary & Context
During production container build on Google Cloud Build (`scripts/fast_deploy.sh`), dependency installation in Step 15 failed immediately with:
```text
Step 15/23 : RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --require-hashes -r <(uv export --format requirements-txt --no-hashes) 2>/dev/null || \
    uv pip install --system --no-cache .
 ---> Running in cdf2548a23b2
/bin/sh: 1: Syntax error: "(" unexpected
The command '/bin/sh -c ...' returned a non-zero code: 2
```

## Symptom & Error Signature
- **Pipeline**: Google Cloud Build (`gcloud builds submit`)
- **Failing Step**: `RUN pip install ... <(...)`
- **Error Signature**: `/bin/sh: 1: Syntax error: "(" unexpected`

## Root Cause Analysis
1. **POSIX Shell Standard vs Bash Extensions**: In Docker, standard `RUN` directives execute commands via `/bin/sh -c` unless explicitly configured with `SHELL ["/bin/bash", "-c"]`.
2. **Dash Default in Debian**: In Debian-based images (`python:3.12-slim`), `/bin/sh` is a symlink to `dash` (Debian Almquist Shell), a minimalist POSIX-compliant shell that strictly conforms to the IEEE 1003.1 standard and deliberately omits non-POSIX Bash extensions.
3. **Bash Process Substitution**: The syntax `<(...)` (process substitution) is a Bash/Zsh-specific extension. When passed to `/bin/sh`, the parenthesis `(` is encountered unexpectedly outside a subshell context, terminating the process with syntax error code 2 before any command is executed.

## Resolution & Architecture Diff
Replace non-portable process substitution with standard POSIX redirection using a temporary file (`-o /tmp/requirements.txt` or `> /tmp/requirements.txt`) followed by immediate cleanup:

```dockerfile
# Before (Broken under /bin/sh):
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache --require-hashes -r <(uv export --format requirements-txt --no-hashes) 2>/dev/null || \
    uv pip install --system --no-cache .

# After (POSIX-compliant across sh, dash, and bash):
RUN pip install --no-cache-dir uv && \
    (uv export --format requirements-txt --no-hashes -o /tmp/requirements.txt 2>/dev/null && \
     uv pip install --system --no-cache -r /tmp/requirements.txt && \
     rm -f /tmp/requirements.txt) || \
    uv pip install --system --no-cache .
```

## Invariants Derived
1. **Dockerfile Shell Portability**: Never assume Bash syntax (`<(...)`, `[[ ... ]]`, `<<<`) in Dockerfile `RUN` instructions unless `SHELL ["/bin/bash", "-c"]` is explicitly declared.
2. **POSIX Redirection for Tool Pipelines**: Always use standard file output (`-o file` or `> file`) with immediate removal for intermediate artifacts in shell pipelines.
