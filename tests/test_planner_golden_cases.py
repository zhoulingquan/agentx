import unittest
from pathlib import Path
import tempfile

from powerbanana.analysis_request import AnalysisTermStore
from powerbanana.evals import PlannerGoldenCaseRunner
from powerbanana.planner import DeterministicDataFilePlanner


class PlannerGoldenCaseTests(unittest.TestCase):
    def test_planner_golden_cases_pass(self):
        summary = PlannerGoldenCaseRunner(Path("evals/planner_cases")).run_all()

        self.assertGreaterEqual(summary.total, 10)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.passed, summary.total)

    def test_planner_golden_case_can_check_analysis_request_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cases_dir = root / "planner_cases"
            cases_dir.mkdir()
            terms_path = root / "analysis_terms.csv"
            terms_path.write_text(
                "kind,value,terms,aggregation,required_columns\n"
                "metric,revenue,revenue|收入,sum,region|revenue\n"
                "group_by,channel,channel|渠道,,\n"
                "group_by,region,region|地区,,\n"
                "rank_direction,highest,highest|最高,,\n",
                encoding="utf-8",
            )
            (cases_dir / "region_revenue.json").write_text(
                """{
  "case_id": "region_revenue",
  "question": "哪个地区收入最高？",
  "expected_scenario": "metric_analysis",
  "expected_min_confidence": 0.8,
  "expected_matched_signals_contains": ["收入"],
  "expected_analysis_request": {
    "metric": "revenue",
    "group_by": "region",
    "rank_direction": "highest"
  }
}
""",
                encoding="utf-8",
            )
            planner = DeterministicDataFilePlanner(analysis_terms=AnalysisTermStore().load_csv(terms_path))

            summary = PlannerGoldenCaseRunner(cases_dir, planner=planner).run_all()

            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.passed, 1)

    def test_planner_golden_case_fails_when_analysis_request_field_differs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cases_dir = root / "planner_cases"
            cases_dir.mkdir()
            terms_path = root / "analysis_terms.csv"
            terms_path.write_text(
                "kind,value,terms,aggregation,required_columns\n"
                "metric,revenue,revenue|收入,sum,region|revenue\n"
                "group_by,region,region|地区,,\n"
                "rank_direction,highest,highest|最高,,\n",
                encoding="utf-8",
            )
            (cases_dir / "wrong_group_by.json").write_text(
                """{
  "case_id": "wrong_group_by",
  "question": "哪个地区收入最高？",
  "expected_scenario": "metric_analysis",
  "expected_matched_signals_contains": ["收入"],
  "expected_analysis_request": {
    "group_by": "country"
  }
}
""",
                encoding="utf-8",
            )
            planner = DeterministicDataFilePlanner(analysis_terms=AnalysisTermStore().load_csv(terms_path))

            summary = PlannerGoldenCaseRunner(cases_dir, planner=planner).run_all()

            self.assertEqual(summary.failed, 1)
            self.assertIn("analysis_request.group_by", summary.results[0].reason)


if __name__ == "__main__":
    unittest.main()
