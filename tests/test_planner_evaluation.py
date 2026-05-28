import unittest

from powerbanana.blackboard import TaskBlackboard
from powerbanana.evaluation import EvaluationRunner
from powerbanana.models import PlannerIntent, PlannerTrace
from powerbanana.planner import DeterministicDataFilePlanner


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


if __name__ == "__main__":
    unittest.main()
