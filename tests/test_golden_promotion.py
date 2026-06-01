import json
import tempfile
import unittest
from pathlib import Path

from powerbanana.analysis_request import AnalysisTermStore
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
                },
                ensure_ascii=False,
                indent=2,
            ),
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


if __name__ == "__main__":
    unittest.main()
