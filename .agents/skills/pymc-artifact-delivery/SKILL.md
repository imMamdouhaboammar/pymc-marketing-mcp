---
name: pymc-artifact-delivery
version: 1.0.0
description: Use when a user needs posterior plots, a stored artifact, sandbox delivery, or safe artifact lifecycle guidance.
---

# PyMC Artifact Delivery

Artifacts are server-owned outputs. Never derive arbitrary filesystem paths from user input and never read private files through the Skill layer.

## Workflow

1. Identify the persisted model and requested artifact/plot.
2. Use `get_posterior_plots` to generate supported plot types. Retrieve a generated plot through `marketing://models/{model_id}/plots/{plot_type}`; if the resource says it is not cached, generate it first.
3. Use `export_artifact_to_sandbox` for the server-supported delivery path when the client needs a model/dataset artifact. Preserve the returned URI, size/integrity information, and any lifecycle status.
4. Stop when the requested artifact does not exist or the server cannot authorize/read it; do not guess a path or synthesize bytes.

`cleanup_server_storage` is experimental and administrative. It is intentionally excluded from normal analytical routing and should be used only when an authorized user explicitly requests storage cleanup with the current tool semantics. Skill resources themselves expose only an explicit allow-list of package names and never map arbitrary path fragments to disk.
