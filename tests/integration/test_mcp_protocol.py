import asyncio
import json

import uvicorn
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.demo_data import generate_synthetic_mmm
from marketing_mcp.mcp.server import create_server


def test_mcp_stdio_client_discovery_and_tools(tmp_path):
    """Verify MCP tool and resource discovery and invocation over stdio transport."""

    async def _run():
        csv_path = tmp_path / "synthetic_mmm.csv"
        generate_synthetic_mmm(n=60).to_csv(csv_path, index=False)

        params = StdioServerParameters(
            command="uv",
            args=["run", "marketing-mcp", "--transport", "stdio"],
            env={
                "MARKETING_MCP_DATA_DIR": str(tmp_path / "data"),
                "MARKETING_MCP_ARTIFACT_DIR": str(tmp_path / "artifacts"),
                "MARKETING_MCP_METADATA_DB": str(tmp_path / "metadata.db"),
                "MARKETING_MCP_INGEST_DIR": str(tmp_path),
            },
        )

        async with (
            stdio_client(params) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()

            # 1. Tool discovery
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            expected_tools = {
                "register_dataset",
                "inspect_dataset",
                "validate_dataset",
                "fit_mmm",
                "get_model_status",
                "diagnose_mmm",
                "get_channel_contributions",
                "get_incremental_roas",
                "get_response_curves",
                "simulate_budget",
                "optimize_budget",
                "recommend_next_measurement",
                "cross_validate_mmm",
                "evaluate_prior_sensitivity",
                "calibrate_mmm",
                "compare_models",
                "archive_model",
                "get_posterior_plots",
                "fit_clv_model",
                "predict_customer_clv",
                "get_churn_risk_cohorts",
                "optimize_flighting",
                "select_best_model",
            }
            assert expected_tools.issubset(tool_names)
            assert "get_skill_guidance" in tool_names

            resources = await session.list_resources()
            resource_uris = {str(r.uri) for r in resources.resources}
            assert "marketing://skills" in resource_uris

            templates = await session.list_resource_templates()
            template_uris = {str(r.uri_template) for r in templates.resource_templates}
            assert "marketing://skills/{skill_name}" in template_uris
            assert "marketing://skills/{skill_name}/manifest" in template_uris

            catalog = await session.read_resource("marketing://skills")
            catalog_data = json.loads(catalog.contents[0].text)
            assert len(catalog_data["skills"]) == 11

            selected = await session.read_resource("marketing://skills/pymc-model-validation")
            assert "# PyMC Model Validation" in selected.contents[0].text
            manifest = await session.read_resource("marketing://skills/pymc-model-validation/manifest")
            manifest_data = json.loads(manifest.contents[0].text)
            assert manifest_data["name"] == "pymc-model-validation"

            routed = await session.call_tool(
                "get_skill_guidance",
                arguments={"task": "Which MMM specification should I trust?"},
            )
            routed_data = json.loads(routed.content[0].text)
            assert routed_data["summary"]["recommended_skill"] == "pymc-model-validation"

            # 2. Tool invocation: register_dataset
            reg_res = await session.call_tool("register_dataset", arguments={"path": str(csv_path)})
            assert len(reg_res.content) > 0
            assert "dataset_id" in reg_res.content[0].text
            reg_data = json.loads(reg_res.content[0].text)
            dataset_id = reg_data["summary"]["dataset_id"]

            # 3. Tool invocation: validate_dataset
            val_res = await session.call_tool(
                "validate_dataset",
                arguments={
                    "dataset_id": dataset_id,
                    "date_column": "date",
                    "target_column": "revenue",
                    "channel_columns": ["meta", "google", "tiktok", "youtube"],
                    "control_columns": ["discount"],
                },
            )
            val_data = json.loads(val_res.content[0].text)
            assert val_data["summary"]["valid_for_modeling"] is True

            # 4. Domain error handling
            err_res = await session.call_tool(
                "get_model_status",
                arguments={"model_id": "non_existent_model"},
            )
            err_data = json.loads(err_res.content[0].text)
            assert err_data["error"]["code"] == "MODEL_NOT_FOUND"

    asyncio.run(_run())


def test_mcp_streamable_http_roundtrip(tmp_path):
    """Verify MCP client handshake, tool call, resource read over Streamable HTTP transport."""

    async def _run():
        app_instance = Application(
            Settings(
                data_dir=tmp_path / "data",
                artifact_dir=tmp_path / "artifacts",
                metadata_db=tmp_path / "metadata.db",
                ingest_dir=tmp_path,
            )
        )
        mcp_server = create_server(app_instance)
        asgi_app = mcp_server.streamable_http_app(host="127.0.0.1")

        config = uvicorn.Config(asgi_app, host="127.0.0.1", port=0, log_level="warning")
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]

        try:
            url = f"http://127.0.0.1:{port}/mcp"
            async with (
                streamable_http_client(url) as (read, write),
                ClientSession(read, write) as session,
            ):
                await session.initialize()

                # List tools
                tools = await session.list_tools()
                assert len(tools.tools) >= 12

                # Invoke recommend_next_measurement on missing model
                res = await session.call_tool(
                    "recommend_next_measurement",
                    arguments={"model_id": "missing_model"},
                )
                err = json.loads(res.content[0].text)
                assert err["error"]["code"] == "MODEL_NOT_FOUND"
        finally:
            server.should_exit = True
            await server_task

    asyncio.run(_run())
