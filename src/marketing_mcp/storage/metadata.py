from __future__ import annotations
import json, sqlite3
from pathlib import Path
from marketing_mcp.errors import DomainError

class SQLiteMetadataStore:
    def __init__(self,path:Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.conn=sqlite3.connect(self.path); self.conn.row_factory=sqlite3.Row; self._init()
    def _init(self):
        self.conn.executescript("CREATE TABLE IF NOT EXISTS datasets (dataset_id TEXT PRIMARY KEY, payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS models (model_id TEXT PRIMARY KEY, payload TEXT NOT NULL); CREATE TABLE IF NOT EXISTS scenarios (scenario_id TEXT PRIMARY KEY, model_id TEXT NOT NULL, payload TEXT NOT NULL);"); self.conn.commit()
    def close(self): self.conn.close()
    def _put(self,table,keycol,key,payload): self.conn.execute(f"INSERT INTO {table}({keycol},payload) VALUES(?,?) ON CONFLICT({keycol}) DO UPDATE SET payload=excluded.payload",(key,json.dumps(payload))); self.conn.commit()
    def _get(self,table,keycol,key,code):
        row=self.conn.execute(f"SELECT payload FROM {table} WHERE {keycol}=?",(key,)).fetchone()
        if not row: raise DomainError(code,f"{key} was not found")
        return json.loads(row["payload"])
    def put_dataset(self,payload): self._put("datasets","dataset_id",payload["dataset_id"],payload)
    def get_dataset(self,dataset_id): return self._get("datasets","dataset_id",dataset_id,"DATASET_NOT_FOUND")
    def put_model(self,payload): self._put("models","model_id",payload["model_id"],payload)
    def get_model(self,model_id): return self._get("models","model_id",model_id,"MODEL_NOT_FOUND")
    def put_scenario(self,payload): self._put("scenarios","scenario_id",payload["scenario_id"],payload)
    def get_scenario(self,scenario_id): return self._get("scenarios","scenario_id",scenario_id,"SCENARIO_NOT_FOUND")
