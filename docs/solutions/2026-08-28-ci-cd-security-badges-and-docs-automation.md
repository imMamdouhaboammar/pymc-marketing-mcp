---
title: "CI/CD Security Hardening, Dynamic Shields Badges via Gist, and Markdown Docs Automation"
category: "CI/CD & Repository Operations"
date: "2026-08-28"
status: "implemented"
tags:
  - "owasp-noir"
  - "dynamic-badges"
  - "markdown-docs"
  - "github-actions"
  - "gh-cli-secrets"
  - "compound-engineering"
  - "loop-engineering"
---

# CI/CD Security Hardening, Dynamic Shields Badges via Gist, and Markdown Docs Automation

## Executive Overview

This document codifies the technical findings, implementation patterns, security hygiene practices, and CI/CD workflow designs from configuring **OWASP Noir** attack-surface mapping, **Dynamic Shields.io Badges** (via Gist automation), and **Markdown Docs** static site deployment for the `pymc-marketing-mcp` repository.

---

## 1. Full Session Chronology (A to Z)

### Phase 1: Attack Surface Discovery & Shadow API Scanning (OWASP Noir)
1. **Requirement**: Automate static route extraction, parameter mapping, and shadow API detection.
2. **Implementation**:
   - Added an `api-surface-scan` job to `.github/workflows/security.yml` using `owasp-noir/noir@v1.3.0`.
   - Configured `path: '.'`, `format: 'json'`, and `output: 'noir-endpoints.json'`.
   - Exported the scan results as a GitHub Actions build artifact (`attack-surface-${{ github.sha }}`).

### Phase 2: Dynamic Shields.io Badges via GitHub Gist
1. **Requirement**: Produce dynamic, auto-updating badges in `README.md` reflecting test status and coverage percentage on every commit to `main`.
2. **Implementation**:
   - Created `.github/workflows/dynamic_badges.yml` leveraging `Schneegans/dynamic-badges-action@v1.9.0`.
   - Configured `pytest-cov` to extract total coverage percentage and test pass/fail state.
   - Bound the workflow to user Gist ID `49445bb38f7e2e299235c6a04299e75f`.
   - Embedded Shields.io endpoint URLs into `README.md` pointing to `pymc_marketing_mcp_tests.json` and `pymc_marketing_mcp_coverage.json`.

### Phase 3: Static Documentation Site Generation (Markdown Docs)
1. **Requirement**: Automatically compile Markdown documentation in `docs/` into a searchable, themed static documentation site.
2. **Implementation**:
   - Created `.github/workflows/docs.yml` using `ldeluigi/markdown-docs@v0.6.0`.
   - Configured input `src: docs` and output `dst: _site`.
   - Added dual publishing: standard GitHub Pages deployment (`actions/deploy-pages@v4`) and standalone zip artifact upload (`actions/upload-artifact@v4`).
   - Added `continue-on-error: true` to the Pages deployment step to handle private repository constraints gracefully.

### Phase 4: Secure Secret Provisioning & Verification
1. **Requirement**: Ensure `GIST_SECRET` is configured in repository secrets with `gist` scope without exposing credentials in logs or shell history.
2. **Implementation**:
   - Verified active GitHub authentication via `gh auth status`.
   - Securely piped the authenticated token into `gh secret set GIST_SECRET --repo imMamdouhaboammar/pymc-marketing-mcp` using in-memory process streams.
   - Verified secret registration via `gh secret list`.
   - Executed full test and lint suites (`ruff`, `check_docs_drift.py`, `generate_capability_inventory.py`, and `pytest`) — 446 tests passed.

---

## 2. Key Challenges & Architectural Resolutions

| Challenge / Constraint | Root Cause | Architectural Resolution |
|---|---|---|
| **Secret Zero-Exposure Invariant** | GitHub Personal Access Tokens must never appear in shell logs, command outputs, or transcripts. | Use piped standard input (`gh auth token \| gh secret set <NAME>`) rather than command-line arguments (`--body`). |
| **Private Repository Pages Limitation** | GitHub Pages for private repositories is restricted to paid plans (HTTP 422). | Maintain dual output in CI: upload `_site` as a downloadable GitHub artifact and set `continue-on-error: true` on `deploy-pages`. |
| **Gist ID Persistence vs. Secret** | Public Gists have fixed IDs, while the auth token is private. | Hardcode the public `gistID` in the workflow and isolate the credential to `secrets.GIST_SECRET`. |
| **Documentation Drift Prevention** | Changing `README.md` or capability signatures can trigger doc drift alarms. | Run `scripts/check_docs_drift.py` and `scripts/generate_capability_inventory.py --check` in the dev loop after any markdown edit. |

---

## 3. Reusable Modules & Learning Chunks

### Chunk A: Zero-Exposure Secret Management Pattern (`/ce-setup`)
```bash
# Securely sync active CLI credentials to GitHub repository secrets without disk/stdout exposure:
gh auth token | gh secret set GIST_SECRET --repo <owner>/<repo>
```

### Chunk B: Gist-Backed Dynamic Badge Pattern (`/loop-engineering`)
```yaml
- name: Dynamic Badge
  uses: Schneegans/dynamic-badges-action@v1.9.0
  with:
    auth: ${{ secrets.GIST_SECRET }}
    gistID: <gist_id>
    filename: <metric_name>.json
    label: <Label>
    message: ${{ steps.calc.outputs.value }}
    color: ${{ steps.calc.outputs.color }}
```

### Chunk C: Resilient Docsite Workflow Pattern
```yaml
# Build with ldeluigi/markdown-docs, save artifact, and attempt Pages deploy
- name: Build Docs
  uses: ldeluigi/markdown-docs@v0.6.0
  with:
    src: docs
    dst: _site
- name: Upload Artifact
  uses: actions/upload-artifact@v4
  with:
    name: docsite
    path: _site
```
