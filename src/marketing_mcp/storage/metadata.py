from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.storage.migrations import MigrationRunner


class SQLiteMetadataStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        runner = MigrationRunner(self.conn)
        runner.apply_pending()

    def close(self):
        self.conn.close()

    def _put(self, table: str, keycol: str, key: str, payload: dict[str, Any]):
        self.conn.execute(
            f"INSERT INTO {table} ({keycol}, payload) VALUES (?, ?) "
            f"ON CONFLICT({keycol}) DO UPDATE SET payload = excluded.payload",
            (key, json.dumps(payload)),
        )
        self.conn.commit()

    def _get(self, table: str, keycol: str, key: str, code: str) -> dict[str, Any]:
        row = self.conn.execute(
            f"SELECT payload FROM {table} WHERE {keycol} = ?", (key,)
        ).fetchone()
        if not row:
            raise DomainError(code, f"{key} was not found")
        return json.loads(row["payload"])

    def put_dataset(self, payload: dict[str, Any]):
        self._put("datasets", "dataset_id", payload["dataset_id"], payload)

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self._get("datasets", "dataset_id", dataset_id, "DATASET_NOT_FOUND")

    def put_model(self, payload: dict[str, Any]):
        self._put("models", "model_id", payload["model_id"], payload)

    def get_model(self, model_id: str) -> dict[str, Any]:
        return self._get("models", "model_id", model_id, "MODEL_NOT_FOUND")

    def put_clv_model(self, payload: dict[str, Any]):
        self._put("clv_models", "model_id", payload["model_id"], payload)

    def get_clv_model(self, model_id: str) -> dict[str, Any]:
        return self._get("clv_models", "model_id", model_id, "CLV_MODEL_NOT_FOUND")

    def put_scenario(self, payload: dict[str, Any]):
        self._put("scenarios", "scenario_id", payload["scenario_id"], payload)

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        return self._get("scenarios", "scenario_id", scenario_id, "SCENARIO_NOT_FOUND")
