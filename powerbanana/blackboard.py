from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import AgentTraceEntry, AnalysisResult, DatasetSnapshot, EvaluationResult, SecurityFinding, StepRecord


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
    artifacts: dict[str, Any] = field(default_factory=dict)

    def record_agent(self, agent_id: str, runtime_mode: str, status: str, output_ref: str) -> None:
        self.agent_trace.append(
            AgentTraceEntry(
                agent_id=agent_id,
                runtime_mode=runtime_mode,
                status=status,
                output_ref=output_ref,
            )
        )
