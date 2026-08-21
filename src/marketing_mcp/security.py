from __future__ import annotations
import re
from pathlib import Path
from .errors import DomainError

_ID=re.compile(r"^[a-zA-Z0-9_-]{1,96}$")
def safe_identifier(value:str, kind:str)->str:
    if not _ID.fullmatch(value):
        raise DomainError("INVALID_IDENTIFIER", f"Invalid {kind} identifier")
    return value

def safe_source_path(path:Path, max_bytes:int)->Path:
    p=path.resolve()
    if p.suffix.lower() not in {".csv",".parquet"}:
        raise DomainError("UNSUPPORTED_DATASET_FORMAT","Only CSV and Parquet are supported")
    if not p.is_file():
        raise DomainError("DATASET_NOT_FOUND","Dataset file does not exist")
    if p.stat().st_size>max_bytes:
        raise DomainError("DATASET_TOO_LARGE",f"Dataset exceeds {max_bytes} bytes")
    return p


def safe_ingest_path(path:Path, ingest_root:Path, max_bytes:int)->Path:
    p=safe_source_path(path,max_bytes)
    root=Path(ingest_root).resolve()
    try:
        p.relative_to(root)
    except ValueError as e:
        raise DomainError("PATH_NOT_ALLOWED","Dataset path must be inside the configured ingest directory",evidence={"ingest_root":str(root)}) from e
    return p
