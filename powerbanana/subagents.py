from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .blackboard import TaskBlackboard
from .context import ContextManager
from .evaluation import EvaluationRunner
from .memory import MemoryManager
from .models import (
    AnalysisResult,
    DatasetSnapshot,
    PowerBananaReport,
    SecurityFinding,
    StepPlan,
    StepPlanStep,
)
from .policies import AutonomyPolicy, default_data_analysis_policy
from .skills import SkillRegistry, build_default_skill_registry, conversion_rate_step_trace
from .tools import ToolGateway


PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore (all )?(previous|prior|above) instructions\b", re.IGNORECASE),
    re.compile(r"\breveal secrets?\b", re.IGNORECASE),
    re.compile(r"\bdisregard (the )?(system|developer) (message|instructions)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class SubAgentProfile:
    agent_id: str
    runtime_mode: str
    role_id: str
    autonomy_level: int | None = None


class DataProfileAgent:
    profile = SubAgentProfile("data_profile_agent", "workflow", "data_profiler")

    def __init__(self, tool_gateway: ToolGateway | None = None) -> None:
        self.tool_gateway = tool_gateway or ToolGateway()

    def run(self, blackboard: TaskBlackboard, path: Path) -> None:
        result = self.tool_gateway.read_dataset_snapshot(path)
        blackboard.rows = result.rows
        blackboard.dataset_snapshot = result.snapshot
        blackboard.record_tool_call(result.tool_call)
        blackboard.security_findings = self._scan_security(result.rows)
        output_ref = blackboard.write_artifact("data_profile_v1", blackboard.dataset_snapshot, self.profile.agent_id, expected_version=0)
        blackboard.record_agent(
            self.profile.agent_id,
            self.profile.runtime_mode,
            "succeeded",
            output_ref,
        )

    def _scan_security(self, rows: list[dict[str, str]]) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for row_index, row in enumerate(rows, start=2):
            for column, value in row.items():
                text = str(value)
                if any(pattern.search(text) for pattern in PROMPT_INJECTION_PATTERNS):
                    findings.append(
                        SecurityFinding(
                            risk_type="prompt_injection_in_cell",
                            source_ref=f"row:{row_index}:column:{column}",
                            action="exclude_as_instruction_keep_as_data",
                            detail=text,
                        )
                    )
        return findings


class DataAnalysisAgent:
    profile = SubAgentProfile("data_analysis_agent", "autonomous", "data_analyst", autonomy_level=2)

    def __init__(
        self,
        skill_registry: SkillRegistry | None = None,
        autonomy_policy: AutonomyPolicy | None = None,
        context_manager: ContextManager | None = None,
        evaluation_runner: EvaluationRunner | None = None,
    ) -> None:
        self.skill_registry = skill_registry or build_default_skill_registry()
        self.autonomy_policy = autonomy_policy or default_data_analysis_policy()
        self.context_manager = context_manager or ContextManager()
        self.evaluation_runner = evaluation_runner or EvaluationRunner()

    def run(self, blackboard: TaskBlackboard) -> None:
        self.context_manager.build_analysis_context(blackboard)
        question = blackboard.question
        if self._is_ambiguous_performance_question(question):
            blackboard.status = "needs_clarification"
            blackboard.answer = "Please specify the metric to optimize, such as conversion_rate, revenue, orders, or visits."
            blackboard.evaluation = self.evaluation_runner.evaluate_gate(
                blackboard,
                verdict="needs_clarification",
                failure_reasons=["ambiguous_metric"],
                gate_action="needs_clarification",
                target_type="clarification_gate",
                target_ref="blackboard://task_001/decisions/clarification_required",
            )
            blackboard.create_human_gate(
                "clarification",
                "ambiguous_metric",
                "Please specify the metric to optimize, such as conversion_rate, revenue, orders, or visits.",
            )
            blackboard.record_agent(self.profile.agent_id, self.profile.runtime_mode, "needs_clarification", "blackboard://task_001/decisions/clarification_required")
            return

        if not self._is_conversion_rate_question(question):
            blackboard.status = "needs_clarification"
            blackboard.answer = "PowerBanana v0.1 supports conversion-rate questions for CSV datasets. Please ask for conversion rate by group."
            blackboard.evaluation = self.evaluation_runner.evaluate_gate(
                blackboard,
                verdict="needs_clarification",
                failure_reasons=["unsupported_question"],
                gate_action="needs_clarification",
                target_type="clarification_gate",
                target_ref="blackboard://task_001/decisions/unsupported_question",
            )
            blackboard.create_human_gate(
                "clarification",
                "unsupported_question",
                "Please ask for a conversion-rate question using channel, visits, and orders.",
            )
            blackboard.record_agent(self.profile.agent_id, self.profile.runtime_mode, "needs_clarification", "blackboard://task_001/decisions/unsupported_question")
            return

        self._answer_conversion_rate(blackboard)

    def _answer_conversion_rate(self, blackboard: TaskBlackboard) -> None:
        snapshot = self._require_snapshot(blackboard)
        required = {"channel", "visits", "orders"}
        missing = sorted(required - set(snapshot.columns))
        if missing:
            blackboard.status = "partial"
            blackboard.answer = f"Cannot compute conversion_rate because required fields are missing: {', '.join(missing)}."
            blackboard.evaluation = self.evaluation_runner.evaluate_gate(
                blackboard,
                verdict="partial",
                failure_reasons=["missing_required_fields"],
                gate_action="return_partial",
                target_type="analysis_precheck",
                target_ref="blackboard://task_001/evaluations/missing_required_fields",
            )
            blackboard.limitations = ["Required fields for conversion_rate are channel, visits, and orders."]
            blackboard.record_agent(self.profile.agent_id, self.profile.runtime_mode, "partial", "blackboard://task_001/evaluations/missing_required_fields")
            return

        step_plan = self._build_conversion_rate_step_plan()
        blackboard.step_plan = step_plan
        self.autonomy_policy.validate_step_plan([step.skill_id for step in step_plan.steps])
        rates, skipped_rows = self.skill_registry.execute("compute_grouped_metric", blackboard.rows)
        blackboard.append_event("skill_executed", self.profile.agent_id, "skill://compute_grouped_metric@0.1.0", {"step_id": "s1"})
        if not rates:
            blackboard.status = "partial"
            blackboard.answer = "Cannot compute conversion_rate because no group has visits greater than zero."
            blackboard.evaluation = self.evaluation_runner.evaluate_gate(
                blackboard,
                verdict="partial",
                failure_reasons=["no_valid_denominator"],
                gate_action="return_partial",
                target_type="analysis_precheck",
                target_ref="blackboard://task_001/evaluations/no_valid_denominator",
            )
            blackboard.limitations = ["At least one row needs a numeric visits value greater than zero."]
            blackboard.record_agent(self.profile.agent_id, self.profile.runtime_mode, "partial", "blackboard://task_001/evaluations/no_valid_denominator")
            return

        top_value, value = self.skill_registry.execute("rank_metric_values", rates)
        blackboard.append_event("skill_executed", self.profile.agent_id, "skill://rank_metric_values@0.1.0", {"step_id": "s2"})
        analysis = AnalysisResult(
            metric="conversion_rate",
            group_by="channel",
            top_value=top_value,
            value=value,
            evidence_ref="blackboard://task_001/artifacts/ranked_metric_result_s2_v1",
            values=rates,
        )
        blackboard.analysis_result = analysis
        blackboard.step_trace = conversion_rate_step_trace(analysis, step_plan)
        blackboard.evaluation = self.evaluation_runner.evaluate_analysis(blackboard)
        blackboard.answer = f"{top_value} has the highest conversion_rate at {value:.2%}."
        blackboard.status = "completed" if blackboard.evaluation.gate_action in {"pass", "pass_with_warning"} else "partial"
        if skipped_rows:
            blackboard.limitations.append(f"Skipped {skipped_rows} rows with missing or nonnumeric channel, visits, or orders.")
        output_ref = blackboard.write_artifact("analysis_result_v1", analysis, self.profile.agent_id, expected_version=0)
        blackboard.record_agent(self.profile.agent_id, self.profile.runtime_mode, blackboard.status, output_ref)

    def _build_conversion_rate_step_plan(self) -> StepPlan:
        return StepPlan(
            step_plan_id="sp_task_001_analysis_v1",
            agent_id=self.profile.agent_id,
            autonomy_level=self.profile.autonomy_level or 0,
            steps=[
                StepPlanStep(
                    step_id="s1",
                    action_type="skill",
                    skill_id="compute_grouped_metric",
                    input_refs=["dataset://task_001/upload_v1"],
                    expected_output_schema="MetricResult",
                    idempotency_key="task_001_upload_v1_s1_compute_grouped_metric",
                ),
                StepPlanStep(
                    step_id="s2",
                    action_type="skill",
                    skill_id="rank_metric_values",
                    input_refs=["blackboard://task_001/artifacts/metric_result_s1_v1"],
                    expected_output_schema="RankedMetricResult",
                    idempotency_key="task_001_upload_v1_s2_rank_metric_values",
                ),
            ],
        )

    def _require_snapshot(self, blackboard: TaskBlackboard) -> DatasetSnapshot:
        if blackboard.dataset_snapshot is None:
            raise ValueError("data_analysis_agent requires data_profile_agent to create a dataset snapshot first.")
        return blackboard.dataset_snapshot

    def _is_ambiguous_performance_question(self, question: str) -> bool:
        q = question.lower()
        return "best" in q and "conversion" not in q and "revenue" not in q and "orders" not in q and "visits" not in q

    def _is_conversion_rate_question(self, question: str) -> bool:
        q = question.lower()
        return "conversion" in q and "rate" in q


class ReportAgent:
    profile = SubAgentProfile("report_agent", "workflow", "report_writer")

    def __init__(self, memory_manager: MemoryManager | None = None) -> None:
        self.memory_manager = memory_manager or MemoryManager()

    def run(self, blackboard: TaskBlackboard, agent_name: str, version: str) -> PowerBananaReport:
        if blackboard.dataset_snapshot is None or blackboard.evaluation is None:
            raise ValueError("report_agent requires dataset_snapshot and evaluation before generating a report.")
        if blackboard.status == "completed":
            self._final_consistency_check(blackboard)
        self.memory_manager.write_task_summary(blackboard)
        blackboard.record_agent(self.profile.agent_id, self.profile.runtime_mode, "succeeded", "blackboard://task_001/artifacts/final_report_v1")
        return PowerBananaReport(
            agent_name=agent_name,
            version=version,
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
            task_plan=blackboard.task_plan,
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

    def _final_consistency_check(self, blackboard: TaskBlackboard) -> None:
        analysis = blackboard.analysis_result
        snapshot = blackboard.dataset_snapshot
        if analysis is None or snapshot is None:
            raise ValueError("Cannot complete final report without analysis result and dataset snapshot.")
        if analysis.group_by not in snapshot.columns:
            blackboard.status = "partial"
            blackboard.limitations.append("Final consistency check failed: group_by field is missing from dataset snapshot.")


def build_default_subagent_registry() -> dict[str, SubAgentProfile]:
    agents = [DataProfileAgent(), DataAnalysisAgent(), ReportAgent()]
    return {agent.profile.agent_id: agent.profile for agent in agents}
