import csv
import tempfile
import unittest
from pathlib import Path

from powerbanana.agent import PowerBananaAgent
from powerbanana.evals import GoldenCaseRunner
from powerbanana.plan import PlanValidator, default_powerbanana_task_plan


class PowerBananaGovernanceTests(unittest.TestCase):
    def write_csv(self, rows):
        handle = tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False)
        with handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return Path(handle.name)

    def test_task_plan_is_validated_frozen_and_reported(self):
        plan = default_powerbanana_task_plan()
        PlanValidator().validate(plan)

        path = self.write_csv(
            [
                {"channel": "email", "visits": "100", "orders": "20"},
                {"channel": "ads", "visits": "200", "orders": "30"},
            ]
        )
        report = PowerBananaAgent().answer(path, "Which channel has the highest conversion rate?")

        self.assertEqual(report.task_plan.status, "frozen")
        self.assertEqual(
            [node.agent_id for node in report.task_plan.nodes],
            ["data_profile_agent", "data_analysis_agent", "report_agent"],
        )

    def test_step_plan_has_idempotency_and_attempt_metadata(self):
        path = self.write_csv(
            [
                {"channel": "email", "visits": "100", "orders": "20"},
                {"channel": "ads", "visits": "200", "orders": "30"},
            ]
        )
        report = PowerBananaAgent().answer(path, "Which channel has the highest conversion rate?")

        self.assertEqual(report.step_plan.step_plan_id, "sp_task_001_analysis_v1")
        self.assertEqual([step.skill_id for step in report.step_plan.steps], ["compute_grouped_metric", "rank_metric_values"])
        self.assertTrue(all(step.idempotency_key for step in report.step_plan.steps))
        self.assertTrue(all(step.attempt_id == "attempt_001" for step in report.step_plan.steps))

    def test_blackboard_tracks_artifact_versions(self):
        path = self.write_csv(
            [
                {"channel": "email", "visits": "100", "orders": "20"},
                {"channel": "ads", "visits": "200", "orders": "30"},
            ]
        )
        report = PowerBananaAgent().answer(path, "Which channel has the highest conversion rate?")

        self.assertEqual(report.artifact_versions["data_profile_v1"], 1)
        self.assertEqual(report.artifact_versions["analysis_result_v1"], 1)
        versioned_events = [
            event for event in report.blackboard_events
            if event.event_type == "artifact_written"
        ]
        self.assertTrue(all("version" in event.detail for event in versioned_events))

    def test_ambiguous_metric_creates_human_gate_record(self):
        path = self.write_csv(
            [
                {"channel": "email", "visits": "100", "orders": "20", "revenue": "500"},
                {"channel": "ads", "visits": "200", "orders": "30", "revenue": "900"},
            ]
        )
        report = PowerBananaAgent().answer(path, "Which channel performs best?")

        self.assertEqual(report.status, "needs_clarification")
        self.assertEqual(len(report.human_gates), 1)
        self.assertEqual(report.human_gates[0].gate_type, "clarification")
        self.assertEqual(report.human_gates[0].status, "pending")
        self.assertIn("human_gate_created", [event.event_type for event in report.blackboard_events])

    def test_golden_case_runner_passes_default_cases(self):
        summary = GoldenCaseRunner(Path("evals/golden_cases")).run_all()

        self.assertGreaterEqual(summary.total, 1)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.passed, summary.total)


if __name__ == "__main__":
    unittest.main()
