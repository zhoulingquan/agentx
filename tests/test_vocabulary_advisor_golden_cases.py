import json
import tempfile
import unittest
from pathlib import Path

from powerbanana.evals import VocabularyAdvisorGoldenCaseRunner


class VocabularyAdvisorGoldenCaseTests(unittest.TestCase):
    def test_vocabulary_advisor_golden_cases_pass(self):
        summary = VocabularyAdvisorGoldenCaseRunner(Path("evals/vocabulary_cases")).run_all()

        self.assertGreaterEqual(summary.total, 6)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.passed, summary.total)

    def test_vocabulary_advisor_golden_case_fails_when_expected_value_differs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cases_dir = Path(tmpdir)
            (cases_dir / "wrong_value.json").write_text(
                json.dumps(
                    {
                        "case_id": "wrong_value",
                        "question": "哪个地区收入最高？",
                        "dataset_columns": ["region", "revenue"],
                        "llm_response": {
                            "should_suggest": True,
                            "suggestion": {
                                "kind": "group_by",
                                "value": "region",
                                "terms": ["地区"],
                                "reason": "region exists in the dataset",
                                "confidence": 0.8,
                            },
                        },
                        "expected_validation_passed": True,
                        "expected_suggestion": {
                            "kind": "group_by",
                            "value": "country",
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            summary = VocabularyAdvisorGoldenCaseRunner(cases_dir).run_all()

        self.assertEqual(summary.total, 1)
        self.assertEqual(summary.failed, 1)
        self.assertIn("suggestion.value", summary.results[0].reason)


if __name__ == "__main__":
    unittest.main()
