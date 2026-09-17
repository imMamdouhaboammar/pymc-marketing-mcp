from __future__ import annotations

from marketing_mcp.app import Application
from marketing_mcp.mcp.resources import register_resources
from marketing_mcp.mcp.tools.artifacts import register_artifacts_tools
from marketing_mcp.mcp.tools.clv import register_clv_tools
from marketing_mcp.mcp.tools.datasets import register_datasets_tools
from marketing_mcp.mcp.tools.decisions import register_decisions_tools
from marketing_mcp.mcp.tools.jobs import register_jobs_tools
from marketing_mcp.mcp.tools.mmm import register_mmm_tools
from marketing_mcp.mcp.tools.model_selection import register_model_selection_tools


def create_server(app: Application | None = None, context_provider=None):
    try:
        from mcp.server.mcpserver import MCPServer
    except ImportError as e:
        raise RuntimeError("Install project dependencies to run the MCP server") from e

    app = app or Application()
    mcp = MCPServer(
        "PyMC Marketing MCP",
        instructions=(
            "Use this server for statistical marketing calculations with PyMC-Marketing. "
            "Never invent or hallucinate posterior estimates. Always diagnose fitted MMMs "
            "before using budget simulation or optimization tools."
        ),
    )

    register_resources(mcp, app, context_provider=context_provider)
    register_clv_tools(mcp, app, context_provider=context_provider)
    register_model_selection_tools(mcp, app, context_provider=context_provider)
    register_decisions_tools(mcp, app, context_provider=context_provider)
    register_mmm_tools(mcp, app, context_provider=context_provider)
    register_datasets_tools(mcp, app, context_provider=context_provider)
    register_jobs_tools(mcp, app, context_provider=context_provider)
    register_artifacts_tools(mcp, app, context_provider=context_provider)

    return mcp
