from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from sqlmodel import Field, Session, SQLModel, create_engine, select


class AuditEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    case_id: str = Field(index=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    tool_name: str = Field(index=True)
    tool_version: str
    args_json: str
    args_sha256: str
    outcome: str
    output_sha256: str
    output_excerpt: str
    duration_ms: int
    agent_iteration: int | None = None
    hypothesis_id: str | None = None


class AuditLog:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        SQLModel.metadata.create_all(self.engine)

    def record(self, *, case_id: str, tool_name: str, tool_version: str,
               args: dict, outcome: str, output: str, duration_ms: int,
               agent_iteration: int | None = None,
               hypothesis_id: str | None = None) -> AuditEntry:
        args_json = json.dumps(args, sort_keys=True, default=str)
        entry = AuditEntry(
            case_id=case_id, tool_name=tool_name, tool_version=tool_version,
            args_json=args_json,
            args_sha256=hashlib.sha256(args_json.encode()).hexdigest(),
            outcome=outcome,
            output_sha256=hashlib.sha256(output.encode()).hexdigest(),
            output_excerpt=output[:2000],
            duration_ms=duration_ms,
            agent_iteration=agent_iteration,
            hypothesis_id=hypothesis_id,
        )
        with Session(self.engine) as s:
            s.add(entry)
            s.commit()
            s.refresh(entry)
        return entry

    def for_case(self, case_id: str) -> list[AuditEntry]:
        with Session(self.engine) as s:
            return list(s.exec(select(AuditEntry).where(
                AuditEntry.case_id == case_id)).all())
