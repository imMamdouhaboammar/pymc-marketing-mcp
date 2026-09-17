from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.storage.migrations import MigrationRunner


class SQLiteMetadataStore:
    def __init__(self, path: Path | str | sqlite3.Connection):
        if isinstance(path, sqlite3.Connection):
            self.conn = path
            self.path = None
        else:
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
            if code == "DATASET_NOT_FOUND":
                next_action = "Register the dataset with register_dataset or check available datasets via list_datasets"
            elif code in ("MODEL_NOT_FOUND", "CLV_MODEL_NOT_FOUND"):
                next_action = "Fit a model first via fit_mmm or fit_clv_model, or verify the model ID with get_model_status"
            else:
                next_action = f"Verify the resource '{key}' exists in table '{table}'"
            raise DomainError(
                code,
                f"{key} was not found",
                evidence={"resource_id": key, "table": table},
                next_action=next_action,
            )
        return json.loads(row["payload"])

    def put_dataset(self, payload: dict[str, Any]):
        self._put("datasets", "dataset_id", payload["dataset_id"], payload)

    def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return self._get("datasets", "dataset_id", dataset_id, "DATASET_NOT_FOUND")

    def list_datasets(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT payload FROM datasets ORDER BY rowid DESC").fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def put_model(self, payload: dict[str, Any]):
        self._put("models", "model_id", payload["model_id"], payload)

    def get_model(self, model_id: str) -> dict[str, Any]:
        return self._get("models", "model_id", model_id, "MODEL_NOT_FOUND")

    def list_models(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT payload FROM models ORDER BY rowid DESC").fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def put_clv_model(self, payload: dict[str, Any]):
        self._put("clv_models", "model_id", payload["model_id"], payload)

    def get_clv_model(self, model_id: str) -> dict[str, Any]:
        return self._get("clv_models", "model_id", model_id, "CLV_MODEL_NOT_FOUND")

    def list_clv_models(self) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT payload FROM clv_models ORDER BY rowid DESC").fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def get_model_unified(self, model_id: str) -> dict[str, Any]:
        """Look up model across both MMM and CLV registries."""
        try:
            return self.get_model(model_id)
        except DomainError:
            try:
                return self.get_clv_model(model_id)
            except DomainError:
                raise DomainError(
                    "MODEL_NOT_FOUND",
                    f"Model '{model_id}' was not found in either MMM or CLV registries",
                    evidence={"model_id": model_id},
                    next_action="Verify the model ID with list_models or fit a model first",
                )

    def list_models_unified(self) -> list[dict[str, Any]]:
        """List all models across both MMM and CLV registries."""
        return self.list_models() + self.list_clv_models()

    def put_scenario(self, payload: dict[str, Any]):
        self._put("scenarios", "scenario_id", payload["scenario_id"], payload)

    def get_scenario(self, scenario_id: str) -> dict[str, Any]:
        return self._get("scenarios", "scenario_id", scenario_id, "SCENARIO_NOT_FOUND")


SQLiteMetadataRepository = SQLiteMetadataStore
