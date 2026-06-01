import json
import tempfile
import unittest
from pathlib import Path

from powerbanana.analysis_request import AnalysisTermStore
from powerbanana.agent import PowerBananaAgent
from powerbanana.evals import GoldenCaseRunner
from powerbanana.golden_promotion import GoldenCasePromoter
from powerbanana.planner import DeterministicDataFilePlanner


class GoldenPromotionTests(unittest.TestCase):
    def write_terms(self, path: Path) -> None:
        path.write_text(
            "kind,value,terms,aggregation,required_columns\n"
            "metric,revenue,revenue|收入,sum,region|revenue\n"
            "group_by,channel,channel|渠道,,\n"
            "group_by,region,region|地区,,\n"
            "rank_direction,highest,highest|最高,,\n",
            encoding="utf-8",
        )

    def write_draft(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "draft_type": "vocabulary_approval_golden_case",
                    "suggestion_id": "vocab_000001",
                    "suggestion": {
                        "target_csv": "config/analysis_terms.csv",
                        "kind": "group_by",
                        "value": "region",
                        "terms": ["地区", "区域"],
                        "reason": "missing_group_by_term",
                        "source": "fake_llm",
                        "confidence": 0.8,
                        "status": "approved",
                    },
                    "planner_case_draft": {
                        "case_id": "region_group_by_metric_analysis",
                        "question": "Replace this with a real user question using one of: 地区|区域",
                        "expected_scenario": "metric_analysis",
                        "expected_min_confidence": 0.8,
                    },
                    "end_to_end_case_draft": {
                        "case_id": "region_group_by_metric_question",
                        "dataset_columns_must_include": ["region"],
                        "expected_group_by": "region",
                        "promotion_note": "Review before promoting.",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def write_dataset(self, path: Path) -> None:
        path.write_text(
            "region,revenue\n"
            "north,500\n"
            "south,900\n",
            encoding="utf-8",
        )

    def test_promotes_reviewed_draft_to_valid_planner_golden_case(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            draft_path = root / "draft.json"
            cases_dir = root / "planner_cases"
            terms_path = root / "analysis_terms.csv"
            self.write_draft(draft_path)
            self.write_terms(terms_path)
            planner = DeterministicDataFilePlanner(analysis_terms=AnalysisTermStore().load_csv(terms_path))

            result = GoldenCasePromoter(planner=planner).promote_planner_case(
                draft_path,
                cases_dir,
                question="哪个地区收入最高？",
                matched_signals=["收入"],
                expected_metric="revenue",
            )

            self.assertTrue(result.validation_passed)
            self.assertTrue(result.case_path.exists())
            data = json.loads(result.case_path.read_text(encoding="utf-8"))
            self.assertEqual(data["question"], "哪个地区收入最高？")
            self.assertEqual(data["expected_analysis_request"]["group_by"], "region")
            self.assertEqual(data["expected_analysis_request"]["metric"], "revenue")

    def test_rejects_placeholder_question_without_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            draft_path = Path(tmpdir) / "draft.json"
            self.write_draft(draft_path)

            with self.assertRaises(ValueError) as error:
                GoldenCasePromoter().promote_planner_case(draft_path, Path(tmpdir) / "planner_cases")

            self.assertIn("requires a real question", str(error.exception))

    def test_golden_case_runner_can_check_analysis_result_fields_with_injected_agent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            cases_dir = root / "golden_cases"
            cases_dir.mkdir()
            terms_path = root / "analysis_terms.csv"
            dataset_path = cases_dir / "region_revenue.csv"
            self.write_terms(terms_path)
            self.write_dataset(dataset_path)
            (cases_dir / "region_revenue.json").write_text(
                json.dumps(
                    {
                        "case_id": "region_revenue",
                        "dataset": "region_revenue.csv",
                        "question": "哪个地区收入最高？",
                        "expected_status": "completed",
                        "expected_answer": "south has the highest revenue at 900.00.",
                        "expected_top_value": "south",
                        "expected_evaluation_verdict": "pass",
                        "expected_gate_action": "pass",
                        "expected_failure_reasons": [],
                        "expected_blocking_issues": [],
                        "expected_security_findings_count": 0,
                        "expected_human_gates_count": 0,
                        "expected_step_skills": ["compute_grouped_metric", "rank_metric_values"],
                        "expected_row_count": 2,
                        "expected_columns": ["region", "revenue"],
                        "expected_analysis_result": {
                            "metric": "revenue",
                            "group_by": "region",
                            "top_value": "south",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            planner = DeterministicDataFilePlanner(analysis_terms=AnalysisTermStore().load_csv(terms_path))
            agent = PowerBananaAgent(planner=planner)

            summary = GoldenCaseRunner(cases_dir, agent=agent).run_all()

            self.assertEqual(summary.failed, 0)
            self.assertEqual(summary.passed, 1)

    def test_promotes_reviewed_draft_to_valid_e2e_golden_case(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            draft_path = root / "draft.json"
            cases_dir = root / "golden_cases"
            terms_path = root / "analysis_terms.csv"
            dataset_path = root / "region_revenue_source.csv"
            self.write_draft(draft_path)
            self.write_terms(terms_path)
            self.write_dataset(dataset_path)
            planner = DeterministicDataFilePlanner(analysis_terms=AnalysisTermStore().load_csv(terms_path))
            agent = PowerBananaAgent(planner=planner)

            result = GoldenCasePromoter(planner=planner, agent=agent).promote_e2e_case(
                draft_path,
                cases_dir,
                dataset_path=dataset_path,
                question="哪个地区收入最高？",
                expected_metric="revenue",
            )

            self.assertTrue(result.validation_passed)
            self.assertTrue(result.case_path.exists())
            self.assertTrue(result.dataset_path.exists())
            data = json.loads(result.case_path.read_text(encoding="utf-8"))
            self.assertEqual(data["expected_answer"], "south has the highest revenue at 900.00.")
            self.assertEqual(data["expected_analysis_result"]["group_by"], "region")
            self.assertEqual(data["expected_analysis_result"]["metric"], "revenue")
            self.assertEqual(data["dataset"], result.dataset_path.name)

    def test_rejects_e2e_promotion_for_placeholder_question(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            draft_path = root / "draft.json"
            dataset_path = root / "region_revenue.csv"
            self.write_draft(draft_path)
            self.write_dataset(dataset_path)

            with self.assertRaises(ValueError) as error:
                GoldenCasePromoter().promote_e2e_case(
                    draft_path,
                    root / "golden_cases",
                    dataset_path=dataset_path,
                )

            self.assertIn("requires a real question", str(error.exception))


if __name__ == "__main__":
    unittest.main()
