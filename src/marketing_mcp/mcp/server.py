from __future__ import annotations

from marketing_mcp.app import Application
from marketing_mcp.mcp.resources import register_resources
from marketing_mcp.mcp.skills import register_skill_delivery
from marketing_mcp.mcp.tools.artifacts import register_artifacts_tools
from marketing_mcp.mcp.tools.clv import register_clv_tools
from marketing_mcp.mcp.tools.datasets import register_datasets_tools
from marketing_mcp.mcp.tools.decisions import register_decisions_tools
from marketing_mcp.mcp.tools.insights import register_insights_tools
from marketing_mcp.mcp.tools.jobs import register_jobs_tools
from marketing_mcp.mcp.tools.mmm import register_mmm_tools
from marketing_mcp.mcp.tools.model_selection import register_model_selection_tools

SERVER_INSTRUCTIONS = (
    "Bayesian marketing science server (media mix modeling, budget decisions, lift calibration, "
    "customer lifetime value) backed by PyMC-Marketing. Operating rules:\n"
    "1. Start every task with get_skill_guidance(task=<the user's request>). It routes to one "
    "workflow skill and returns its guidance inline: tool order, argument templates, gates, "
    "error recovery, and how to explain results to marketers. Follow it.\n"
    "2. Check existing state before creating new work: list_datasets, list_jobs, "
    "get_model_status. The server keeps datasets, models, and jobs across sessions.\n"
    "3. Every model-dependent number (contributions, iROAS, response, allocations, CLV, "
    "diagnostics) must come from a tool result. Never estimate them yourself.\n"
    "4. diagnose_mmm must approve a model before get_incremental_roas, simulate_budget, "
    "optimize_budget, or optimize_flighting. A rejected model gets no budget answer.\n"
    "5. Remote clients: send data as content, content_base64, or a public url; path means a "
    "file on the server. Use submit_*_job tools with an idempotency_key for fits, "
    "cross-validation, and prior sensitivity, and poll at most three times in a row.\n"
    "6. Keep every warning, interval, and caution status in the answer. Keep user budget "
    "constraints exactly; report conflicts instead of relaxing them.\n"
    "Shared references: get_skill_guidance(reference_name='agent-operating-protocol') and "
    "get_skill_guidance(reference_name='marketing-decision-playbook')."
)


def create_server(app: Application | None = None, context_provider=None):
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as e:
        raise RuntimeError("Install project dependencies to run the MCP server") from e

    app = app or Application()
    mcp = MCPServer(
        "PyMC Marketing MCP",
        instructions=SERVER_INSTRUCTIONS,
    )

    register_resources(mcp, app, context_provider=context_provider)
    register_clv_tools(mcp, app, context_provider=context_provider)
    register_model_selection_tools(mcp, app, context_provider=context_provider)
    register_decisions_tools(mcp, app, context_provider=context_provider)
    register_mmm_tools(mcp, app, context_provider=context_provider)
    register_datasets_tools(mcp, app, context_provider=context_provider)
    register_jobs_tools(mcp, app, context_provider=context_provider)
    register_artifacts_tools(mcp, app, context_provider=context_provider)
    register_insights_tools(mcp, app, context_provider=context_provider)
    register_skill_delivery(mcp, app, context_provider=context_provider)

    return mcp


# Compatibility alias
create_mcp_server = create_server
