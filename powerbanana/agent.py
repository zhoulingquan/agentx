from __future__ import annotations

from pathlib import Path

from .blackboard import TaskBlackboard
from .dag import TaskDagExecutor
from .evaluation import EvaluationRunner
from .llm import default_llm_settings
from .models import PowerBananaReport
from .plan import PlanValidator
from .planner import DeterministicDataFilePlanner, Planner
from .subagents import DataAnalysisAgent, DataProfileAgent, ReportAgent


class PowerBananaAgent:
    name = "PowerBanana"
    version = "0.1"

    def __init__(
        self,
        data_profile_agent: DataProfileAgent | None = None,
        data_analysis_agent: DataAnalysisAgent | None = None,
        report_agent: ReportAgent | None = None,
        evaluation_runner: EvaluationRunner | None = None,
        planner: Planner | None = None,
    ) -> None:
        self.data_profile_agent = data_profile_agent or DataProfileAgent()
        self.data_analysis_agent = data_analysis_agent or DataAnalysisAgent(evaluation_runner=evaluation_runner)
        self.report_agent = report_agent or ReportAgent()
        self.planner = planner or DeterministicDataFilePlanner()

    def answer(self, file_path: str | Path, question: str) -> PowerBananaReport:
        path = Path(file_path)
        blackboard = TaskBlackboard(question=question)
        blackboard.llm_settings = default_llm_settings()
        planner_result = self.planner.plan(path, question)
        blackboard.record_planner_trace(planner_result.trace)
        blackboard.task_plan = PlanValidator().validate(planner_result.candidate_plan)
        task_dag = TaskDagExecutor(blackboard.task_plan.nodes)
        result = task_dag.run(
            blackboard,
            {
                "data_profile_agent": self.data_profile_agent.run,
                "data_analysis_agent": self.data_analysis_agent.run,
                "report_agent": self.report_agent.run,
            },
            path,
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
            blackboard_entries=blackboard.entries,
            task_plan=blackboard.task_plan,
            planner_trace=blackboard.planner_trace,
            step_plan=blackboard.step_plan,
            artifact_versions=blackboard.artifact_versions,
            human_gates=blackboard.human_gates,
            tool_calls=blackboard.tool_calls,
            context_bundle=blackboard.context_bundle,
            memory_records=blackboard.memory_records,
            llm_settings=blackboard.llm_settings,
            step_trace=blackboard.step_trace,
            evaluation=blackboard.evaluation,
            analysis_result=blackboard.analysis_result,
            limitations=blackboard.limitations,
        )
