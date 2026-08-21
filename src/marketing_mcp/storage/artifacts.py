from __future__ import annotations
from pathlib import Path
from marketing_mcp.security import safe_identifier
from marketing_mcp.errors import DomainError

class LocalArtifactStore:
    def __init__(self,root:Path): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def model_path(self,model_id:str)->Path:
        safe_identifier(model_id,"model"); return self.root/f"{model_id}.nc"
    def require(self,model_id:str)->Path:
        p=self.model_path(model_id)
        if not p.exists(): raise DomainError("BROKEN_ARTIFACT","The fitted model artifact is missing",evidence={"path":str(p)})
        return p
