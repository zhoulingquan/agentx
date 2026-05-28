from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any

from .models import (
    AgentTraceEntry,
    AnalysisResult,
    BlackboardEntry,
    BlackboardEvent,
    ContextBundle,
    DagNodeTrace,
    DatasetSnapshot,
    EvaluationResult,
    HumanGateRecord,
    LLMSettings,
    MemoryRecord,
    PlannerTrace,
    SecurityFinding,
    StepPlan,
    StepRecord,
    TaskPlan,
    ToolCallRecord,
)


@dataclass
class TaskBlackboard:
    task_id: str = "task_001"
    status: str = "created"
    task_plan: TaskPlan | None = None
    planner_trace: PlannerTrace | None = None
    rows: list[dict[str, str]] = field(default_factory=list)
    question: str = ""
    dataset_snapshot: DatasetSnapshot | None = None
    security_findings: list[SecurityFinding] = field(default_factory=list)
    analysis_result: AnalysisResult | None = None
    planner_evaluation: EvaluationResult | None = None
    evaluation: EvaluationResult | None = None
    answer: str = ""
    limitations: list[str] = field(default_factory=list)
    step_plan: StepPlan | None = None
    step_trace: list[StepRecord] = field(default_factory=list)
    agent_trace: list[AgentTraceEntry] = field(default_factory=list)
    dag_trace: list[DagNodeTrace] = field(default_factory=list)
    events: list[BlackboardEvent] = field(default_factory=list)
    entries: list[BlackboardEntry] = field(default_factory=list)
    artifact_versions: dict[str, int] = field(default_factory=dict)
    human_gates: list[HumanGateRecord] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    context_bundle: ContextBundle | None = None
    memory_records: list[MemoryRecord] = field(default_factory=list)
    llm_settings: LLMSettings | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.append_event("blackboard_created", "main_agent", f"blackboard://{self.task_id}", {"status": self.status})

    def append_event(self, event_type: str, actor_id: str, target_ref: str, detail: dict[str, Any] | None = None) -> BlackboardEvent:
        event = BlackboardEvent(
            event_id=f"evt_{len(self.events) + 1:04d}",
            event_type=event_type,
            actor_id=actor_id,
            target_ref=target_ref,
            detail=detail or {},
        )
        self.events.append(event)
        return event

    def write_entry(
        self,
        entry_type: str,
        owner_agent_id: str,
        source_ref: str,
        target_ref: str,
        payload: Any,
        visibility_scope: list[str] | None = None,
        confidence: float = 1.0,
        version: int = 1,
    ) -> BlackboardEntry:
        entry_id = f"entry_{len(self.entries) + 1:04d}"
        event = self.append_event(
            "entry_written",
            owner_agent_id,
            target_ref,
            {"entry_id": entry_id, "entry_type": entry_type, "version": version},
        )
        entry = BlackboardEntry(
            entry_id=entry_id,
            entry_type=entry_type,
            owner_agent_id=owner_agent_id,
            source_ref=source_ref,
            target_ref=target_ref,
            visibility_scope=visibility_scope or ["task"],
            confidence=confidence,
            version=version,
            payload=self._serialize_payload(payload),
            audit_ref=event.event_id,
        )
        self.entries.append(entry)
        return entry

    def write_artifact(self, artifact_id: str, value: Any, actor_id: str, expected_version: int | None = None) -> str:
        current_version = self.artifact_versions.get(artifact_id, 0)
        if expected_version is not None and expected_version != current_version:
            raise ValueError(
                f"Artifact version mismatch for {artifact_id}: expected {expected_version}, got {current_version}."
            )
        next_version = current_version + 1
        self.artifact_versions[artifact_id] = next_version
        self.artifacts[artifact_id] = value
        target_ref = f"blackboard://{self.task_id}/artifacts/{artifact_id}"
        self.append_event(
            "artifact_written",
            actor_id,
            target_ref,
            {
                "artifact_id": artifact_id,
                "version": next_version,
                "expected_version": expected_version,
            },
        )
        self.write_entry(
            entry_type="artifact",
            owner_agent_id=actor_id,
            source_ref=f"agent://{actor_id}",
            target_ref=target_ref,
            payload=value,
            visibility_scope=["task", "assigned_agents"],
            confidence=1.0,
            version=next_version,
        )
        return target_ref

    def record_security_finding(self, finding: SecurityFinding, actor_id: str) -> str:
        self.security_findings.append(finding)
        target_ref = f"blackboard://{self.task_id}/security_findings/security_finding_{len(self.security_findings):03d}"
        self.write_entry(
            entry_type="security_finding",
            owner_agent_id=actor_id,
            source_ref=finding.source_ref,
            target_ref=target_ref,
            payload=finding,
            visibility_scope=["task", "security_review"],
            confidence=0.9,
        )
        return target_ref

    def record_evaluation(self, evaluation: EvaluationResult, actor_id: str = "evaluation_layer") -> str:
        self.evaluation = evaluation
        target_ref = evaluation.target_ref or f"blackboard://{self.task_id}/evaluations/{evaluation.evaluation_id}"
        self.write_entry(
            entry_type="evaluation",
            owner_agent_id=actor_id,
            source_ref=f"evaluation://{evaluation.evaluation_id}",
            target_ref=target_ref,
            payload=evaluation,
            visibility_scope=["task", "evaluation"],
            confidence=1.0,
        )
        return target_ref

    def record_planner_evaluation(self, evaluation: EvaluationResult, actor_id: str = "evaluation_layer") -> str:
        self.planner_evaluation = evaluation
        target_ref = evaluation.target_ref or f"blackboard://{self.task_id}/evaluations/{evaluation.evaluation_id}"
        self.write_entry(
            entry_type="evaluation",
            owner_agent_id=actor_id,
            source_ref=f"evaluation://{evaluation.evaluation_id}",
            target_ref=target_ref,
            payload=evaluation,
            visibility_scope=["task", "planning", "evaluation"],
            confidence=1.0,
        )
        return target_ref

    def record_planner_trace(self, trace: PlannerTrace, actor_id: str = "planner") -> str:
        self.planner_trace = trace
        target_ref = f"blackboard://{self.task_id}/planner/{trace.candidate_plan_id}"
        self.write_entry(
            entry_type="planner_trace",
            owner_agent_id=actor_id,
            source_ref=f"planner://{trace.planner_id}",
            target_ref=target_ref,
            payload=trace,
            visibility_scope=["task", "planning"],
            confidence=1.0,
        )
        return target_ref

    def record_agent(self, agent_id: str, runtime_mode: str, status: str, output_ref: str) -> None:
        self.agent_trace.append(
            AgentTraceEntry(
                agent_id=agent_id,
                runtime_mode=runtime_mode,
                status=status,
                output_ref=output_ref,
            )
        )
        self.append_event("agent_completed", agent_id, output_ref, {"runtime_mode": runtime_mode, "status": status})

    def record_dag_node(self, node_id: str, agent_id: str, status: str, depends_on: list[str]) -> None:
        self.dag_trace.append(DagNodeTrace(node_id=node_id, agent_id=agent_id, status=status, depends_on=depends_on))
        self.append_event("dag_node_transition", "main_agent", f"dag://{node_id}", {"status": status, "agent_id": agent_id})

    def record_tool_call(self, record: ToolCallRecord) -> None:
        self.tool_calls.append(record)
        self.append_event("tool_called", "tool_gateway", record.output_ref, {"tool_id": record.tool_id, "status": record.status})

    def set_context_bundle(self, bundle: ContextBundle) -> None:
        self.context_bundle = bundle
        self.append_event("context_bundle_created", "context_manager", f"context://{bundle.context_bundle_id}", {"agent_id": bundle.agent_id})

    def write_memory(self, record: MemoryRecord) -> None:
        self.memory_records.append(record)
        self.append_event("memory_written", "memory_manager", f"memory://{record.memory_id}", {"memory_type": record.memory_type})

    def create_human_gate(self, gate_type: str, reason: str, prompt: str) -> HumanGateRecord:
        record = HumanGateRecord(
            gate_id=f"gate_{len(self.human_gates) + 1:03d}",
            gate_type=gate_type,
            status="pending",
            reason=reason,
            prompt=prompt,
        )
        self.human_gates.append(record)
        self.append_event("human_gate_created", "human_gate", f"gate://{record.gate_id}", {"gate_type": gate_type, "reason": reason})
        return record

    def _serialize_payload(self, value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, list):
            return [self._serialize_payload(item) for item in value]
        if isinstance(value, dict):
            return {key: self._serialize_payload(item) for key, item in value.items()}
        return value
