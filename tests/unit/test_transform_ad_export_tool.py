from __future__ import annotations

import asyncio
import json

import pandas as pd

from marketing_mcp.app import Application
from marketing_mcp.config import Settings
from marketing_mcp.mcp.context import ExecutionContext
from marketing_mcp.mcp.server import create_server
from marketing_mcp.security.principal import Principal


def _app(tmp_path):
    return Application(
        Settings(
            data_dir=tmp_path / "data",
            artifact_dir=tmp_path / "artifacts",
            metadata_db=tmp_path / "metadata.db",
            ingest_dir=tmp_path,
        )
    )


def _provider_for(principal):
    return lambda: ExecutionContext(principal=principal)


def _call(server, tool, args):
    result = asyncio.run(server.call_tool(tool, args))
    item = result[0] if isinstance(result, list) else getattr(result, "content", [None])[0]
    if item is None:
        raise AssertionError(f"unexpected call_tool result: {result!r}")
    text = getattr(item, "text", None) or str(item)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def test_transform_ad_export_tool_success_and_tenant_isolation(tmp_path):
    app = _app(tmp_path)
    raw_data = [
        {"date": "2026-01-01", "geo": "US", "platform": "Google Ads", "spend": 100.0, "revenue": 300.0, "impressions": 1000, "clicks": 50, "ctr": 0.05},
        {"date": "2026-01-01", "geo": "US", "platform": "TikTok Ads", "spend": 80.0, "revenue": 160.0, "impressions": 2000, "clicks": 40, "ctr": 0.02},
        {"date": "2026-01-02", "geo": "US", "platform": "Google Ads", "spend": 120.0, "revenue": 360.0, "impressions": 1200, "clicks": 60, "ctr": 0.05},
    ]
    df = pd.DataFrame(raw_data)
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    principal = Principal(
        subject="user-corp",
        tenant_id="tenant-corp",
        scopes=frozenset({"marketing:model", "marketing:read"}),
        auth_type="api_key",
    )
    reg = app.datasets.register_bytes(
        csv_bytes,
        format="csv",
        filename="raw_ads.csv",
        principal=principal,
    )
    dataset_id = reg.dataset_id

    server = create_server(app, context_provider=_provider_for(principal))

    # 1. Successful transformation call
    payload = {
        "dataset_id": dataset_id,
        "date_column": "date",
        "channel_column": "platform",
        "spend_column": "spend",
        "target_columns": ["revenue"],
        "dimension_columns": ["geo"],
        "frequency": "D",
    }
    resp = _call(server, "transform_ad_export", payload)

    assert "summary" in resp
    assert resp["summary"]["spend_reconciled"] is True
    assert resp["summary"]["spend_delta"] == 0.0
    assert "google_ads_spend" in resp["evidence"]["provenance"]["channel_columns_created"]
    assert "tiktok_ads_spend" in resp["evidence"]["provenance"]["channel_columns_created"]
    assert resp["next_actions"] == ["inspect_dataset", "validate_dataset"]

    transformed_id = resp["summary"]["transformed_dataset_id"]
    t_ds = app.metadata.get_dataset(transformed_id, tenant_id=principal.tenant_id)
    assert t_ds is not None
    assert t_ds["rows"] == 2

    # 2. Adversary from different tenant cannot transform this dataset
    adversary = Principal(
        subject="hacker",
        tenant_id="tenant-other",
        scopes=frozenset({"marketing:model", "marketing:read"}),
        auth_type="api_key",
    )
    server_adv = create_server(app, context_provider=_provider_for(adversary))
    adv_resp = _call(server_adv, "transform_ad_export", payload)

    assert "error" in adv_resp or adv_resp.get("code") in ("DATASET_NOT_FOUND", "AUTH_FORBIDDEN")

    # 3. Direct delegate exercise
    registered_res, prov, plan = app.datasets.transform_long_form(
        dataset_id=reg.dataset_id,
        date_column="date",
        channel_column="platform",
        spend_column="spend",
        target_columns=["revenue"],
        dimension_columns=["geo"],
        frequency="D",
        principal=principal,
    )
    assert prov.spend_reconciled is True
