from __future__ import annotations

from pathlib import Path

from .blackboard import TaskBlackboard
from .models import PowerBananaReport
from .subagents import DataAnalysisAgent, DataProfileAgent, ReportAgent


class PowerBananaAgent:
    name = "PowerBanana"
    version = "0.1"

    def __init__(
        self,
        data_profile_agent: DataProfileAgent | None = None,
        data_analysis_agent: DataAnalysisAgent | None = None,
        report_agent: ReportAgent | None = None,
    ) -> None:
        self.data_profile_agent = data_profile_agent or DataProfileAgent()
        self.data_analysis_agent = data_analysis_agent or DataAnalysisAgent()
        self.report_agent = report_agent or ReportAgent()

    def answer(self, file_path: str | Path, question: str) -> PowerBananaReport:
        blackboard = TaskBlackboard(question=question)
        self.data_profile_agent.run(blackboard, Path(file_path))
        self.data_analysis_agent.run(blackboard)
        if blackboard.status == "needs_clarification":
            return self._clarification_report(blackboard)
        return self.report_agent.run(blackboard, self.name, self.version)

    def _clarification_report(self, blackboard: TaskBlackboard) -> PowerBananaReport:
        if blackboard.dataset_snapshot is None or blackboard.evaluation is None:
            raise ValueError("Clarification reports require dataset_snapshot and evaluation.")
        return PowerBananaReport(
            agent_name=self.name,
            version=self.version,
            status=blackboard.status,
            answer=blackboard.answer,
            dataset_snapshot=blackboard.dataset_snapshot,
            security_findings=blackboard.security_findings,
            agent_trace=blackboard.agent_trace,
            step_trace=blackboard.step_trace,
            evaluation=blackboard.evaluation,
            analysis_result=blackboard.analysis_result,
            limitations=blackboard.limitations,
        )
