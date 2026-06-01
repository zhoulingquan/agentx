from __future__ import annotations

from pathlib import Path

from .blackboard import TaskBlackboard
from .dag import TaskDagExecutor
from .evaluation import EvaluationRunner
from .llm import default_llm_settings
from .models import LLMSettings, PowerBananaReport
from .plan import PlanValidator
from .planner import DeterministicDataFilePlanner, Planner
from .subagents import DataAnalysisAgent, DataProfileAgent, ReportAgent
from .vocabulary import LLMVocabularyAdvisor, NullVocabularyAdvisor


EXECUTABLE_PLANNER_SCENARIOS = {"metric_analysis", "conversion_rate_analysis"}

PLANNER_ROUTE_MESSAGES = {
    "ambiguous_metric": {
        "failure_reason": "ambiguous_metric",
        "answer": "Please specify the metric to optimize, such as conversion_rate, revenue, orders, or visits.",
        "prompt": "Please specify the metric to optimize, such as conversion_rate, revenue, orders, or visits.",
    },
    "unsupported_forecast": {
        "failure_reason": "unsupported_question",
        "answer": "PowerBanana v0.1 does not support forecasting yet. Please ask for conversion rate by group.",
        "prompt": "Please ask for a supported conversion-rate question by group.",
    },
    "unknown": {
        "failure_reason": "unknown_scenario",
        "answer": "PowerBanana could not classify this question. Please ask for a supported channel metric question.",
        "prompt": "Please rephrase as a supported channel metric question.",
    },
}


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
        vocabulary_advisor: LLMVocabularyAdvisor | None = None,
    ) -> None:
        self.evaluation_runner = evaluation_runner or EvaluationRunner()
        self.data_profile_agent = data_profile_agent or DataProfileAgent()
        self.data_analysis_agent = data_analysis_agent or DataAnalysisAgent(
            evaluation_runner=self.evaluation_runner,
            vocabulary_advisor=vocabulary_advisor,
        )
        self.report_agent = report_agent or ReportAgent()
        self.planner = planner or DeterministicDataFilePlanner()
        self.llm_settings = self._llm_settings_for_vocabulary_advisor(vocabulary_advisor)

    def answer(self, file_path: str | Path, question: str) -> PowerBananaReport:
        path = Path(file_path)
        blackboard = TaskBlackboard(question=question)
        blackboard.llm_settings = self.llm_settings
        planner_result = self.planner.plan(path, question)
        blackboard.record_planner_trace(planner_result.trace)
        blackboard.record_planner_evaluation(self.evaluation_runner.evaluate_planner_trace(blackboard))
        if blackboard.planner_evaluation.gate_action == "block":
            return self._planner_blocked_report(blackboard)
        if self._should_route_from_planner(blackboard):
            return self._planner_routed_report(blackboard)
        blackboard.task_plan = PlanValidator().validate(planner_result.candidate_plan)
        task_dag = TaskDagExecutor.from_plan(blackboard.task_plan)
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

    def _should_route_from_planner(self, blackboard: TaskBlackboard) -> bool:
        intent = blackboard.planner_trace.intent if blackboard.planner_trace else None
        if intent:
            scenario_id = intent.scenario_id
        elif blackboard.planner_trace:
            scenario_id = blackboard.planner_trace.scenario_id
        else:
            scenario_id = "unknown"
        return scenario_id not in EXECUTABLE_PLANNER_SCENARIOS

    def _llm_settings_for_vocabulary_advisor(self, vocabulary_advisor: LLMVocabularyAdvisor | None) -> LLMSettings:
        if vocabulary_advisor is None or isinstance(vocabulary_advisor, NullVocabularyAdvisor):
            return default_llm_settings()
        return LLMSettings(
            provider=str(getattr(vocabulary_advisor, "provider", "external_vocabulary_advisor")),
            model=str(getattr(vocabulary_advisor, "model", "unknown")),
            temperature=float(getattr(vocabulary_advisor, "temperature", 0.0)),
            mode="vocabulary_suggestion_only",
            max_tokens=int(getattr(vocabulary_advisor, "max_tokens", 0)),
        )

    def _planner_routed_report(self, blackboard: TaskBlackboard) -> PowerBananaReport:
        if blackboard.planner_trace is None or blackboard.planner_evaluation is None:
            raise ValueError("Planner routed reports require planner_trace and planner_evaluation.")
        intent = blackboard.planner_trace.intent
        scenario_id = intent.scenario_id if intent else blackboard.planner_trace.scenario_id
        route = PLANNER_ROUTE_MESSAGES.get(
            scenario_id,
            {
                "failure_reason": "unsupported_question",
                "answer": "PowerBanana v0.1 supports channel metric questions for CSV datasets.",
                "prompt": "Please ask for a channel metric question using conversion_rate, revenue, orders, or visits.",
            },
        )
        target_ref = f"blackboard://{blackboard.task_id}/planner/{blackboard.planner_trace.candidate_plan_id}/routing"
        failure_reason = route["failure_reason"]
        warnings = list(intent.warnings if intent else blackboard.planner_trace.warnings)
        blackboard.status = "needs_clarification"
        blackboard.answer = route["answer"]
        blackboard.limitations = ["Planner routed before dataset loading."]
        blackboard.record_evaluation(
            self.evaluation_runner.evaluate_gate(
                blackboard,
                verdict="needs_clarification",
                failure_reasons=[failure_reason],
                gate_action="needs_clarification",
                target_type="planner_routing_gate",
                target_ref=target_ref,
                scores={"planner_routing": 1.0},
                warnings=warnings,
            )
        )
        blackboard.create_human_gate("clarification", failure_reason, route["prompt"])
        blackboard.append_event(
            "planner_routed",
            "main_agent",
            target_ref,
            {
                "scenario_id": scenario_id,
                "gate_action": "needs_clarification",
                "failure_reasons": [failure_reason],
            },
        )
        return PowerBananaReport(
            agent_name=self.name,
            version=self.version,
            status=blackboard.status,
            answer=blackboard.answer,
            dataset_snapshot=None,
            security_findings=blackboard.security_findings,
            agent_trace=blackboard.agent_trace,
            dag_trace=blackboard.dag_trace,
            blackboard_events=blackboard.events,
            blackboard_entries=blackboard.entries,
            task_plan=blackboard.task_plan,
            planner_trace=blackboard.planner_trace,
            planner_evaluation=blackboard.planner_evaluation,
            step_plan=blackboard.step_plan,
            artifact_versions=blackboard.artifact_versions,
            human_gates=blackboard.human_gates,
            vocabulary_suggestions=blackboard.vocabulary_suggestions,
            tool_calls=blackboard.tool_calls,
            context_bundle=blackboard.context_bundle,
            memory_records=blackboard.memory_records,
            llm_settings=blackboard.llm_settings,
            step_trace=blackboard.step_trace,
            evaluation=blackboard.evaluation,
            analysis_result=blackboard.analysis_result,
            limitations=blackboard.limitations,
        )

    def _planner_blocked_report(self, blackboard: TaskBlackboard) -> PowerBananaReport:
        if blackboard.planner_evaluation is None:
            raise ValueError("Blocked planner reports require planner_evaluation.")
        blackboard.status = "blocked"
        reasons = ", ".join(blackboard.planner_evaluation.failure_reasons)
        blackboard.answer = f"Planner evaluation blocked execution: {reasons}."
        blackboard.limitations = blackboard.planner_evaluation.blocking_issues
        blackboard.evaluation = blackboard.planner_evaluation
        blackboard.append_event(
            "planner_blocked",
            "main_agent",
            blackboard.planner_evaluation.target_ref,
            {
                "gate_action": blackboard.planner_evaluation.gate_action,
                "failure_reasons": blackboard.planner_evaluation.failure_reasons,
            },
        )
        return PowerBananaReport(
            agent_name=self.name,
            version=self.version,
            status=blackboard.status,
            answer=blackboard.answer,
            dataset_snapshot=None,
            security_findings=blackboard.security_findings,
            agent_trace=blackboard.agent_trace,
            dag_trace=blackboard.dag_trace,
            blackboard_events=blackboard.events,
            blackboard_entries=blackboard.entries,
            task_plan=blackboard.task_plan,
            planner_trace=blackboard.planner_trace,
            planner_evaluation=blackboard.planner_evaluation,
            step_plan=blackboard.step_plan,
            artifact_versions=blackboard.artifact_versions,
            human_gates=blackboard.human_gates,
            vocabulary_suggestions=blackboard.vocabulary_suggestions,
            tool_calls=blackboard.tool_calls,
            context_bundle=blackboard.context_bundle,
            memory_records=blackboard.memory_records,
            llm_settings=blackboard.llm_settings,
            step_trace=blackboard.step_trace,
            evaluation=blackboard.planner_evaluation,
            analysis_result=blackboard.analysis_result,
            limitations=blackboard.limitations,
        )

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
            planner_evaluation=blackboard.planner_evaluation,
            step_plan=blackboard.step_plan,
            artifact_versions=blackboard.artifact_versions,
            human_gates=blackboard.human_gates,
            vocabulary_suggestions=blackboard.vocabulary_suggestions,
            tool_calls=blackboard.tool_calls,
            context_bundle=blackboard.context_bundle,
            memory_records=blackboard.memory_records,
            llm_settings=blackboard.llm_settings,
            step_trace=blackboard.step_trace,
            evaluation=blackboard.evaluation,
            analysis_result=blackboard.analysis_result,
            limitations=blackboard.limitations,
        )
