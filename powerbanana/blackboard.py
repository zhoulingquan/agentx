from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import (
    AgentTraceEntry,
    AnalysisResult,
    BlackboardEvent,
    DagNodeTrace,
    DatasetSnapshot,
    EvaluationResult,
    SecurityFinding,
    StepRecord,
)


@dataclass
class TaskBlackboard:
    task_id: str = "task_001"
    status: str = "created"
    rows: list[dict[str, str]] = field(default_factory=list)
    question: str = ""
    dataset_snapshot: DatasetSnapshot | None = None
    security_findings: list[SecurityFinding] = field(default_factory=list)
    analysis_result: AnalysisResult | None = None
    evaluation: EvaluationResult | None = None
    answer: str = ""
    limitations: list[str] = field(default_factory=list)
    step_trace: list[StepRecord] = field(default_factory=list)
    agent_trace: list[AgentTraceEntry] = field(default_factory=list)
    dag_trace: list[DagNodeTrace] = field(default_factory=list)
    events: list[BlackboardEvent] = field(default_factory=list)
    artifacts: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.append_event("blackboard_created", "main_agent", f"blackboard://{self.task_id}", {"status": self.status})

    def append_event(self, event_type: str, actor_id: str, target_ref: str, detail: dict[str, Any] | None = None) -> None:
        self.events.append(
            BlackboardEvent(
                event_id=f"evt_{len(self.events) + 1:04d}",
                event_type=event_type,
                actor_id=actor_id,
                target_ref=target_ref,
                detail=detail or {},
            )
        )

    def write_artifact(self, artifact_id: str, value: Any, actor_id: str) -> str:
        self.artifacts[artifact_id] = value
        target_ref = f"blackboard://{self.task_id}/artifacts/{artifact_id}"
        self.append_event("artifact_written", actor_id, target_ref, {"artifact_id": artifact_id})
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
