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
    attempt_id: str = "attempt_001"
    idempotency_key: str = ""


@dataclass(frozen=True)
class StepPlanStep:
    step_id: str
    action_type: str
    skill_id: str
    input_refs: list[str]
    expected_output_schema: str
    idempotency_key: str
    attempt_id: str = "attempt_001"
    status: str = "pending"


@dataclass(frozen=True)
class StepPlan:
    step_plan_id: str
    agent_id: str
    autonomy_level: int
    steps: list[StepPlanStep]
    status: str = "validated"


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
class TaskPlanNode:
    node_id: str
    agent_id: str
    runtime_mode: str
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TaskPlan:
    plan_id: str
    scenario_id: str
    status: str
    nodes: list[TaskPlanNode]


@dataclass(frozen=True)
class HumanGateRecord:
    gate_id: str
    gate_type: str
    status: str
    reason: str
    prompt: str


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
    evaluation_id: str = "eval_001"
    evaluator_version: str = "legacy"
    target_type: str = "analysis_result"
    target_ref: str = ""
    status: str = "completed"
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    gate_action: str = "pass"
    evidence_refs: list[str] = field(default_factory=list)
    evaluator_results: list[dict[str, Any]] = field(default_factory=list)
    snapshot_ref: str = ""


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
    task_plan: TaskPlan | None = None
    step_plan: StepPlan | None = None
    artifact_versions: dict[str, int] = field(default_factory=dict)
    human_gates: list[HumanGateRecord] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    context_bundle: ContextBundle | None = None
    memory_records: list[MemoryRecord] = field(default_factory=list)
    llm_settings: LLMSettings | None = None
    analysis_result: AnalysisResult | None = None
    limitations: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
