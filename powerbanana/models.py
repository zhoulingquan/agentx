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
class DagNodeTrace:
    node_id: str
    agent_id: str
    status: str
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BlackboardEvent:
    event_id: str
    event_type: str
    actor_id: str
    target_ref: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallRecord:
    tool_id: str
    status: str
    risk_level: str
    input_ref: str
    output_ref: str


@dataclass(frozen=True)
class ContextItem:
    ref: str
    trust_level: str
    allowed_use: str


@dataclass(frozen=True)
class ContextBundle:
    context_bundle_id: str
    agent_id: str
    items: list[ContextItem]
    max_tokens: int


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    scope: str
    layer: str
    memory_type: str
    content: dict[str, Any]


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    temperature: float
    mode: str
    max_tokens: int


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
    dag_trace: list[DagNodeTrace]
    blackboard_events: list[BlackboardEvent]
    step_trace: list[StepRecord]
    evaluation: EvaluationResult
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    context_bundle: ContextBundle | None = None
    memory_records: list[MemoryRecord] = field(default_factory=list)
    llm_settings: LLMSettings | None = None
    analysis_result: AnalysisResult | None = None
    limitations: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
