from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DatasetSnapshot:
    dataset_id: str
    dataset_version: str
    file_hash: str
    row_count: int
    columns: list[str]
    missing_counts: dict[str, int]


@dataclass(frozen=True)
class SecurityFinding:
    risk_type: str
    source_ref: str
    action: str
    detail: str


@dataclass(frozen=True)
class StepRecord:
    step_id: str
    action_type: str
    skill_id: str
    status: str
    input_refs: list[str]
    output_ref: str
    expected_output_schema: str


@dataclass(frozen=True)
class AgentTraceEntry:
    agent_id: str
    runtime_mode: str
    status: str
    output_ref: str


@dataclass(frozen=True)
class AnalysisResult:
    metric: str
    group_by: str
    top_value: str
    value: float
    evidence_ref: str
    values: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationResult:
    verdict: str
    failure_reasons: list[str]
    scores: dict[str, float]


@dataclass(frozen=True)
class PowerBananaReport:
    agent_name: str
    version: str
    status: str
    answer: str
    dataset_snapshot: DatasetSnapshot
    security_findings: list[SecurityFinding]
    agent_trace: list[AgentTraceEntry]
    step_trace: list[StepRecord]
    evaluation: EvaluationResult
    analysis_result: AnalysisResult | None = None
    limitations: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
