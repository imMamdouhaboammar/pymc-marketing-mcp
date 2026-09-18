import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from marketing_mcp.errors import DomainError
from marketing_mcp.storage.migrations import MigrationRunner


class SQLiteMetadataStore:
    def __init__(self, path: Path | str | sqlite3.Connection):
        self._lock = threading.RLock()
        if isinstance(path, sqlite3.Connection):
            self.conn = path
            self.path = None
        else:
            self.path = Path(path)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        with self._lock:
            self.conn.execute("PRAGMA journal_mode = WAL;")
            self.conn.execute("PRAGMA synchronous = NORMAL;")
            self.conn.execute("PRAGMA busy_timeout = 30000;")
            runner = MigrationRunner(self.conn)
            runner.apply_pending()

    def close(self):
        with self._lock:
            self.conn.close()

    def _put(self, table: str, keycol: str, key: str, payload: dict[str, Any], tenant_id: str | None = None):
        with self._lock:
            t_id = tenant_id if tenant_id is not None else payload.get("tenant_id")
            # Check if table has tenant_id column
            has_tenant = "tenant_id" in [c[1] for c in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if has_tenant:
                self.conn.execute(
                    f"INSERT INTO {table} ({keycol}, tenant_id, payload) VALUES (?, ?, ?) "
                    f"ON CONFLICT({keycol}) DO UPDATE SET tenant_id = excluded.tenant_id, payload = excluded.payload",
                    (key, t_id, json.dumps(payload)),
                )
            else:
                self.conn.execute(
                    f"INSERT INTO {table} ({keycol}, payload) VALUES (?, ?) "
                    f"ON CONFLICT({keycol}) DO UPDATE SET payload = excluded.payload",
                    (key, json.dumps(payload)),
                )
            if self.conn.in_transaction:
                self.conn.commit()

    def _get(self, table: str, keycol: str, key: str, code: str, tenant_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            query = f"SELECT payload FROM {table} WHERE {keycol} = ?"
            params: list[Any] = [key]
            has_tenant = "tenant_id" in [c[1] for c in self.conn.execute(f"PRAGMA table_info({table})").fetchall()]
            if has_tenant and tenant_id is not None:
                if tenant_id in (None, "default"):
                    query += " AND (tenant_id = 'default' OR tenant_id IS NULL)"
                else:
                    query += " AND tenant_id = ?"
                    params.append(tenant_id)
            row = self.conn.execute(query, params).fetchone()
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

    def put_dataset(self, payload: dict[str, Any], tenant_id: str | None = None):
        self._put("datasets", "dataset_id", payload["dataset_id"], payload, tenant_id=tenant_id)

    def get_dataset(self, dataset_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        return self._get("datasets", "dataset_id", dataset_id, "DATASET_NOT_FOUND", tenant_id=tenant_id)

    def list_datasets(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            query = "SELECT payload FROM datasets"
            params: list[Any] = []
            has_tenant = "tenant_id" in [c[1] for c in self.conn.execute("PRAGMA table_info(datasets)").fetchall()]
            if has_tenant and tenant_id is not None:
                if tenant_id in (None, "default"):
                    query += " WHERE (tenant_id = 'default' OR tenant_id IS NULL)"
                else:
                    query += " WHERE tenant_id = ?"
                    params.append(tenant_id)
            query += " ORDER BY rowid DESC"
            rows = self.conn.execute(query, params).fetchall()
            return [json.loads(r["payload"]) for r in rows]

    def put_model(self, payload: dict[str, Any], tenant_id: str | None = None):
        self._put("models", "model_id", payload["model_id"], payload, tenant_id=tenant_id)

    def get_model(self, model_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        return self._get("models", "model_id", model_id, "MODEL_NOT_FOUND", tenant_id=tenant_id)

    def list_models(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            query = "SELECT payload FROM models"
            params: list[Any] = []
            has_tenant = "tenant_id" in [c[1] for c in self.conn.execute("PRAGMA table_info(models)").fetchall()]
            if has_tenant and tenant_id is not None:
                if tenant_id in (None, "default"):
                    query += " WHERE (tenant_id = 'default' OR tenant_id IS NULL)"
                else:
                    query += " WHERE tenant_id = ?"
                    params.append(tenant_id)
            query += " ORDER BY rowid DESC"
            rows = self.conn.execute(query, params).fetchall()
            return [json.loads(r["payload"]) for r in rows]

    def put_clv_model(self, payload: dict[str, Any], tenant_id: str | None = None):
        self._put("clv_models", "model_id", payload["model_id"], payload, tenant_id=tenant_id)

    def get_clv_model(self, model_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        return self._get("clv_models", "model_id", model_id, "CLV_MODEL_NOT_FOUND", tenant_id=tenant_id)

    def list_clv_models(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            query = "SELECT payload FROM clv_models"
            params: list[Any] = []
            has_tenant = "tenant_id" in [c[1] for c in self.conn.execute("PRAGMA table_info(clv_models)").fetchall()]
            if has_tenant and tenant_id is not None:
                if tenant_id in (None, "default"):
                    query += " WHERE (tenant_id = 'default' OR tenant_id IS NULL)"
                else:
                    query += " WHERE tenant_id = ?"
                    params.append(tenant_id)
            query += " ORDER BY rowid DESC"
            rows = self.conn.execute(query, params).fetchall()
            return [json.loads(r["payload"]) for r in rows]

    def get_model_unified(self, model_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        """Look up model across both MMM and CLV registries."""
        try:
            return self.get_model(model_id, tenant_id=tenant_id)
        except DomainError:
            try:
                return self.get_clv_model(model_id, tenant_id=tenant_id)
            except DomainError:
                raise DomainError(
                    "MODEL_NOT_FOUND",
                    f"Model '{model_id}' was not found in either MMM or CLV registries",
                    evidence={"model_id": model_id},
                    next_action="Verify the model ID with list_models or fit a model first",
                )

    def list_models_unified(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """List all models across both MMM and CLV registries."""
        return self.list_models(tenant_id=tenant_id) + self.list_clv_models(tenant_id=tenant_id)

    def put_scenario(self, payload: dict[str, Any], tenant_id: str | None = None):
        self._put("scenarios", "scenario_id", payload["scenario_id"], payload, tenant_id=tenant_id)

    def get_scenario(self, scenario_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        return self._get("scenarios", "scenario_id", scenario_id, "SCENARIO_NOT_FOUND", tenant_id=tenant_id)

    def put_insight(self, payload: dict[str, Any]) -> None:
        tags = payload.get("tags")
        tags_str = json.dumps(tags) if isinstance(tags, (list, dict)) else (tags or "[]")
        self.conn.execute(
            """
            INSERT INTO agent_insights (
                insight_id, tenant_id, agent_id, category, severity,
                summary, details, model_id, dataset_id, tags, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(insight_id) DO UPDATE SET
                tenant_id = excluded.tenant_id,
                agent_id = excluded.agent_id,
                category = excluded.category,
                severity = excluded.severity,
                summary = excluded.summary,
                details = excluded.details,
                model_id = excluded.model_id,
                dataset_id = excluded.dataset_id,
                tags = excluded.tags,
                created_at = excluded.created_at
            """,
            (
                payload["insight_id"],
                payload["tenant_id"],
                payload["agent_id"],
                payload["category"],
                payload.get("severity", "info"),
                payload["summary"],
                payload.get("details"),
                payload.get("model_id"),
                payload.get("dataset_id"),
                tags_str,
                payload["created_at"],
            ),
        )
        self.conn.commit()

    def get_insight(self, tenant_id: str, insight_id: str) -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM agent_insights WHERE tenant_id = ? AND insight_id = ?",
            (tenant_id, insight_id),
        ).fetchone()
        if not row:
            raise DomainError(
                "INSIGHT_NOT_FOUND",
                f"Insight '{insight_id}' was not found for active tenant",
                evidence={"insight_id": insight_id, "tenant_id": tenant_id},
                next_action="Verify the insight_id or use get_agent_insights to list recent records",
            )
        d = dict(row)
        if d.get("tags"):
            try:
                d["tags"] = json.loads(d["tags"])
            except Exception:
                pass
        return d

    def list_insights(
        self,
        tenant_id: str,
        model_id: str | None = None,
        dataset_id: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM agent_insights WHERE tenant_id = ?"
        params: list[Any] = [tenant_id]
        if model_id:
            query += " AND model_id = ?"
            params.append(model_id)
        if dataset_id:
            query += " AND dataset_id = ?"
            params.append(dataset_id)
        if category:
            query += " AND category = ?"
            params.append(category)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("tags"):
                try:
                    d["tags"] = json.loads(d["tags"])
                except Exception:
                    pass
            if tag and isinstance(d.get("tags"), list) and tag not in d["tags"]:
                continue
            results.append(d)
        return results

    def put_mapping_profile(self, profile_data: dict[str, Any], tenant_id: str | None = None) -> None:
        org_id = tenant_id or profile_data.get("organization_id") or "default"
        mappings_json = (
            json.dumps(profile_data["mappings"])
            if isinstance(profile_data["mappings"], (dict, list))
            else str(profile_data["mappings"])
        )
        now = datetime.now(UTC).isoformat()
        created_at = profile_data.get("created_at") or now
        updated_at = profile_data.get("updated_at") or now

        with self._lock:
            self.conn.execute(
                """
                INSERT INTO organization_mapping_profiles (
                    profile_id, organization_id, profile_name, mappings, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_id) DO UPDATE SET
                    profile_name = excluded.profile_name,
                    mappings = excluded.mappings,
                    updated_at = excluded.updated_at
                """,
                (
                    profile_data["profile_id"],
                    org_id,
                    profile_data["profile_name"],
                    mappings_json,
                    created_at,
                    updated_at,
                ),
            )
            self.conn.commit()

    def get_mapping_profile(self, profile_id: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM organization_mapping_profiles WHERE profile_id = ?"
        params: list[Any] = [profile_id]
        if tenant_id is not None:
            query += " AND organization_id = ?"
            params.append(tenant_id)
        with self._lock:
            row = self.conn.execute(query, params).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("mappings"):
            try:
                d["mappings"] = json.loads(d["mappings"])
            except Exception:
                pass
        return d

    def get_mapping_profile_by_name(self, profile_name: str, tenant_id: str | None = None) -> dict[str, Any] | None:
        query = "SELECT * FROM organization_mapping_profiles WHERE profile_name = ?"
        params: list[Any] = [profile_name]
        if tenant_id is not None:
            query += " AND organization_id = ?"
            params.append(tenant_id)
        with self._lock:
            row = self.conn.execute(query, params).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("mappings"):
            try:
                d["mappings"] = json.loads(d["mappings"])
            except Exception:
                pass
        return d

    def list_mapping_profiles(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM organization_mapping_profiles"
        params: list[Any] = []
        if tenant_id is not None:
            query += " WHERE organization_id = ?"
            params.append(tenant_id)
        query += " ORDER BY updated_at DESC"
        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            if d.get("mappings"):
                try:
                    d["mappings"] = json.loads(d["mappings"])
                except Exception:
                    pass
            results.append(d)
        return results

    def delete_mapping_profile(self, profile_id: str, tenant_id: str | None = None) -> bool:
        query = "DELETE FROM organization_mapping_profiles WHERE profile_id = ?"
        params: list[Any] = [profile_id]
        if tenant_id is not None:
            query += " AND organization_id = ?"
            params.append(tenant_id)
        with self._lock:
            cursor = self.conn.execute(query, params)
            self.conn.commit()
            return cursor.rowcount > 0


    def put_experiment(self, payload: dict[str, Any], tenant_id: str | None = None) -> None:
        exp_id = payload["experiment_id"]
        t_id = tenant_id or payload.get("tenant_id") or "default"
        ch = payload.get("channel", "")
        payload_str = json.dumps(payload)

        with self._lock:
            # Check immutability
            existing = self.conn.execute(
                "SELECT payload FROM experiments WHERE experiment_id = ?",
                (exp_id,),
            ).fetchone()
            if existing is not None:
                existing_payload = json.loads(existing["payload"])
                # Disallow altering scientific parameters or channel
                for field in ("channel", "baseline_spend", "spend_delta", "measured_incremental_response", "standard_error"):
                    if field in payload and payload[field] != existing_payload.get(field):
                        raise DomainError(
                            "IMMUTABLE_EVIDENCE_VIOLATION",
                            f"Experiment evidence '{exp_id}' is immutable and cannot alter parameter '{field}'",
                            evidence={"experiment_id": exp_id, "field": field},
                            next_action="Register a new experiment ID rather than mutating historic evidence",
                        )

            self.conn.execute(
                """
                INSERT INTO experiments (experiment_id, tenant_id, channel, archived, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(experiment_id) DO UPDATE SET
                    payload = excluded.payload,
                    archived = excluded.archived
                """,
                (exp_id, t_id, ch, int(payload.get("archived", False)), payload_str),
            )
            self.conn.commit()

    def get_experiment(self, experiment_id: str, tenant_id: str | None = None) -> dict[str, Any]:
        query = "SELECT payload FROM experiments WHERE experiment_id = ?"
        params: list[Any] = [experiment_id]
        if tenant_id is not None:
            if tenant_id in (None, "default"):
                query += " AND (tenant_id = 'default' OR tenant_id IS NULL)"
            else:
                query += " AND tenant_id = ?"
                params.append(tenant_id)
        with self._lock:
            row = self.conn.execute(query, params).fetchone()
        if not row:
            raise DomainError(
                "EXPERIMENT_NOT_FOUND",
                f"Experiment '{experiment_id}' was not found in evidence registry",
                evidence={"experiment_id": experiment_id, "tenant_id": tenant_id},
                next_action="Register the experiment first via register_experiment",
            )
        return json.loads(row["payload"])

    def list_experiments(
        self,
        tenant_id: str | None = None,
        channel: str | None = None,
        include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        query = "SELECT payload FROM experiments WHERE 1=1"
        params: list[Any] = []
        if tenant_id is not None:
            if tenant_id in (None, "default"):
                query += " AND (tenant_id = 'default' OR tenant_id IS NULL)"
            else:
                query += " AND tenant_id = ?"
                params.append(tenant_id)
        if channel is not None:
            query += " AND channel = ?"
            params.append(channel)
        if not include_archived:
            query += " AND archived = 0"
        query += " ORDER BY rowid DESC"

        with self._lock:
            rows = self.conn.execute(query, params).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def archive_experiment(self, experiment_id: str, tenant_id: str | None = None) -> None:
        record = self.get_experiment(experiment_id, tenant_id=tenant_id)
        record["archived"] = True
        with self._lock:
            self.conn.execute(
                "UPDATE experiments SET archived = 1, payload = ? WHERE experiment_id = ?",
                (json.dumps(record), experiment_id),
            )
            self.conn.commit()


SQLiteMetadataRepository = SQLiteMetadataStore
