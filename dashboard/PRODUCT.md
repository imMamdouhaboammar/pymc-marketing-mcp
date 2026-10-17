# Public teaser

English teaser for marketers, owners, e-commerce managers, agency strategists, and analysts deciding whether to try PyMC Marketing MCP. Visitor mode: Persuade.

Outcome: understand the upstream library and MCP bridge, recognize a relevant decision, and reach a truthful synthetic-data starting path. The existing authenticated console remains outside the redesign.

| Section | Visitor question | Content and action | Composition / narrow screens |
| --- | --- | --- | --- |
| Hero + example | What does this help me do? | Evidence behind a marketing decision; labeled illustrative scenario; Try the sample workflow | Centered large type, then one analytical brief; brief stacks |
| Science + connection | What is the library, and what is the MCP? | Plain-language definitions and source links | Two editorial columns; one column on mobile |
| Your work | How would I use it? | Five role-specific questions, inputs, outputs, and copyable prompts | Vertical React Aria tabs + shared panel; wrapping horizontal tabs on mobile |
| Evidence | What supports the result? | Library computation, diagnostic policy, provenance, current beta limits | Quiet warm surface; no score simulator |
| Try it | How do I begin? | Prerequisites, synthetic CLI demo, local client configuration, selected prompt | Three ordered steps; code wraps within its own region |
| FAQ + close | What should I know first? | Four objections; repeat the same starting action | Editorial accordion; compact close |

Alternative considered: split-screen hero with a chat mockup. Chosen: centered editorial hero with one analytical brief, following Prepilot's hierarchy without pretending the public page runs a model.

## Claim sources

| Public claim | Authority / qualification |
| --- | --- |
| MMM, scenarios, CLV | `src/marketing_mcp/capabilities.py`, `docs/TOOL-CONTRACTS.md`; no expanded upstream-only features |
| Diagnostic conditions on decisions | `docs/DECISION-INTEGRITY.md`; approval is not causal certainty |
| Evidence and model identity | Current tool contracts and persistence behavior; no universal reproducibility guarantee |
| Advanced beta, not release-approved | `docs/PRODUCTION-READINESS.md`; link instead of copied gate counts |
| Local setup | README, `pyproject.toml`, `src/marketing_mcp/demo.py`, actual CLI help; synthetic MMM only, with no CLV transaction sample and no guaranteed fitted model |
| Claude Desktop local stdio | Official local-MCP guide and server stdio transport; one absolute project path in `uv --directory`, with dataset, artifact, metadata, and ingest paths sharing `.demo-runtime` |

Illustrative preview contains no numerical results, identifies itself as an example, and states that no model has run. The local smoke demo may stop before a fitted model is available; the selected prompt and setup keep that prerequisite visible. No testimonials, partner marks, tool totals, release version literals, hosted trial claims, or fake compatibility lists.

UI ownership: `TeaserLandingPage` owns selected role; `CopyBlock` owns asynchronous clipboard status and manual fallback; React Aria owns tabs and disclosures. Existing `AuthProvider` and authenticated console keep their current ownership. Public CSS is scoped under `.teaser-site`.
