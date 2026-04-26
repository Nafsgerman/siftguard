from __future__ import annotations
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class EvidencePath(BaseModel):
    path: str = Field(description="Path relative to evidence root")

    @field_validator("path")
    @classmethod
    def no_traversal(cls, v: str) -> str:
        p = Path(v)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("Path must be relative and contain no '..'")
        return v


class MFTEntry(BaseModel):
    record_number: int
    in_use: bool
    file_type: Literal["File", "Directory"]
    full_path: str
    file_size: int
    si_created: datetime | None
    si_modified: datetime | None
    si_accessed: datetime | None
    si_entry_modified: datetime | None
    fn_created: datetime | None
    fn_modified: datetime | None
    timestomp_suspected: bool = Field(
        description="True when SI and FN timestamps differ suspiciously"
    )


class PrefetchEntry(BaseModel):
    executable_name: str
    run_count: int
    last_run_times: list[datetime]
    referenced_files: list[str] = Field(default_factory=list)
    hash: str


class VolatilityProcess(BaseModel):
    pid: int
    ppid: int
    name: str
    create_time: datetime | None
    exit_time: datetime | None
    threads: int
    handles: int | None
    suspicious_indicators: list[str] = Field(default_factory=list)


class ToolOutcome(str, Enum):
    OK = "ok"
    PARTIAL = "partial"
    FAIL = "fail"


class ForensicResult(BaseModel):
    tool: str
    outcome: ToolOutcome
    summary: str
    findings: list[dict] = Field(default_factory=list)
    raw_excerpt: str | None = Field(default=None, max_length=2000)
    evidence_refs: list[str] = Field(default_factory=list)
    duration_ms: int
    error: str | None = None
