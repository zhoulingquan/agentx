from __future__ import annotations

from pathlib import Path

from .blackboard import TaskBlackboard
from .dag import TaskDagExecutor, default_powerbanana_task_dag
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
        self.task_dag = TaskDagExecutor(default_powerbanana_task_dag())

    def answer(self, file_path: str | Path, question: str) -> PowerBananaReport:
        blackboard = TaskBlackboard(question=question)
        result = self.task_dag.run(
            blackboard,
            {
                "data_profile_agent": self.data_profile_agent.run,
                "data_analysis_agent": self.data_analysis_agent.run,
                "report_agent": self.report_agent.run,
            },
            Path(file_path),
            {"agent_name": self.name, "version": self.version},
        )
        if isinstance(result, PowerBananaReport):
            return result
        return self._clarification_report(blackboard)

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
            dag_trace=[
                node
                for node in blackboard.dag_trace
                if node.status != "running"
            ],
            blackboard_events=blackboard.events,
            step_trace=blackboard.step_trace,
            evaluation=blackboard.evaluation,
            analysis_result=blackboard.analysis_result,
            limitations=blackboard.limitations,
        )
