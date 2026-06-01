import unittest

from powerbanana.agent import PowerBananaAgent
from powerbanana.blackboard import TaskBlackboard
from powerbanana.evaluation import EvaluationRunner
from powerbanana.models import PlannerIntent, PlannerTrace
from powerbanana.plan import default_powerbanana_task_plan
from powerbanana.planner import DeterministicDataFilePlanner
from powerbanana.planner import PlannerResult


class MissingIntentPlanner:
    planner_id = "missing_intent_planner"
    planner_mode = "deterministic_no_llm"

    def plan(self, file_path, question):
        return PlannerResult(
            candidate_plan=default_powerbanana_task_plan(),
            trace=PlannerTrace(
                planner_id=self.planner_id,
                planner_mode=self.planner_mode,
                status="candidate_created",
                scenario_id="conversion_rate_analysis",
                candidate_plan_id="plan_test_missing_intent",
                rationale="test blocked planner trace",
            ),
        )


class ExplodingDataProfileAgent:
    def run(self, blackboard, path):
        raise AssertionError("DAG should not run when planner evaluation blocks.")


class PlannerEvaluationTests(unittest.TestCase):
    def test_planner_intent_evaluation_passes_for_valid_conversion_intent(self):
        blackboard = TaskBlackboard(question="Which channel has the highest conversion rate?")
        planner_result = DeterministicDataFilePlanner().plan(
            "sample.csv",
            blackboard.question,
        )
        blackboard.record_planner_trace(planner_result.trace)

        result = EvaluationRunner().evaluate_planner_trace(blackboard)

        self.assertEqual(result.target_type, "planner_trace")
        self.assertEqual(result.gate_action, "pass")
        self.assertEqual(result.verdict, "pass")
        self.assertEqual(result.scores["planner_intent"], 1.0)

    def test_planner_intent_evaluation_blocks_missing_intent(self):
        blackboard = TaskBlackboard(question="Which channel has the highest conversion rate?")
        blackboard.record_planner_trace(
            PlannerTrace(
                planner_id="test_planner",
                planner_mode="deterministic_no_llm",
                status="candidate_created",
                scenario_id="conversion_rate_analysis",
                candidate_plan_id="plan_test",
                rationale="test",
            )
        )

        result = EvaluationRunner().evaluate_planner_trace(blackboard)

        self.assertEqual(result.gate_action, "block")
        self.assertIn("missing_planner_intent", result.failure_reasons)

    def test_planner_intent_evaluation_blocks_missing_required_warning(self):
        blackboard = TaskBlackboard(question="Can you forecast conversion rate next month?")
        blackboard.record_planner_trace(
            PlannerTrace(
                planner_id="test_planner",
                planner_mode="deterministic_no_llm",
                status="candidate_created",
                scenario_id="unsupported_forecast",
                candidate_plan_id="plan_test",
                rationale="test",
                intent=PlannerIntent(
                    scenario_id="unsupported_forecast",
                    confidence=0.9,
                    matched_signals=["forecast"],
                    warnings=[],
                ),
            )
        )

        result = EvaluationRunner().evaluate_planner_trace(blackboard)

        self.assertEqual(result.gate_action, "block")
        self.assertIn("missing_unsupported_warning", result.failure_reasons)

    def test_agent_returns_blocked_report_without_running_dag_when_planner_gate_blocks(self):
        report = PowerBananaAgent(
            data_profile_agent=ExplodingDataProfileAgent(),
            planner=MissingIntentPlanner(),
        ).answer("sample.csv", "Which channel has the highest conversion rate?")

        self.assertEqual(report.status, "blocked")
        self.assertIsNone(report.task_plan)
        self.assertIsNone(report.dataset_snapshot)
        self.assertEqual(report.dag_trace, [])
        self.assertEqual(report.agent_trace, [])
        self.assertEqual(report.planner_evaluation.gate_action, "block")
        self.assertEqual(report.evaluation.target_type, "planner_trace")
        self.assertIn("planner_blocked", [event.event_type for event in report.blackboard_events])

    def test_agent_routes_non_executable_planner_scenarios_without_running_dag(self):
        cases = [
            (
                "Which channel performs best?",
                "ambiguous_metric",
                "ambiguous_metric",
                "Please specify the metric",
            ),
            (
                "Can you forecast conversion rate next month?",
                "unsupported_forecast",
                "unsupported_question",
                "does not support forecasting",
            ),
            (
                "Which channel has the highest revenue?",
                "unsupported_revenue",
                "unsupported_question",
                "does not support revenue analysis",
            ),
            (
                "Summarize this upload.",
                "unknown",
                "unknown_scenario",
                "could not classify",
            ),
        ]

        for question, scenario_id, failure_reason, answer_fragment in cases:
            with self.subTest(question=question):
                report = PowerBananaAgent(data_profile_agent=ExplodingDataProfileAgent()).answer(
                    "missing.csv",
                    question,
                )

                self.assertEqual(report.status, "needs_clarification")
                self.assertIsNone(report.task_plan)
                self.assertIsNone(report.dataset_snapshot)
                self.assertEqual(report.dag_trace, [])
                self.assertEqual(report.agent_trace, [])
                self.assertEqual(report.step_trace, [])
                self.assertEqual(report.planner_trace.intent.scenario_id, scenario_id)
                self.assertEqual(report.planner_evaluation.gate_action, "pass")
                self.assertEqual(report.evaluation.target_type, "planner_routing_gate")
                self.assertEqual(report.evaluation.gate_action, "needs_clarification")
                self.assertIn(failure_reason, report.evaluation.failure_reasons)
                self.assertIn(answer_fragment, report.answer)
                self.assertEqual(report.human_gates[0].gate_type, "clarification")
                self.assertIn("planner_routed", [event.event_type for event in report.blackboard_events])


if __name__ == "__main__":
    unittest.main()
