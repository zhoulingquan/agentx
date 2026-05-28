import json
import tempfile
import unittest
from pathlib import Path

from powerbanana.planner_lexicon import (
    LexiconStore,
    LexiconSuggestionBuilder,
    PlannerClassifier,
    default_planner_lexicon,
)


class PlannerLexiconTests(unittest.TestCase):
    def test_default_lexicon_classifies_conversion_rate(self):
        intent = PlannerClassifier(default_planner_lexicon()).classify(
            "Which channel has the highest conversion rate?"
        )

        self.assertEqual(intent.scenario_id, "conversion_rate_analysis")
        self.assertGreaterEqual(intent.confidence, 0.8)
        self.assertIn("conversion", intent.matched_signals)
        self.assertIn("rate", intent.matched_signals)

    def test_default_lexicon_marks_ambiguous_metric(self):
        intent = PlannerClassifier(default_planner_lexicon()).classify(
            "Which channel performs best?"
        )

        self.assertEqual(intent.scenario_id, "ambiguous_metric")
        self.assertIn("missing_metric", intent.warnings)

    def test_negative_terms_can_redirect_to_unsupported_scenario(self):
        intent = PlannerClassifier(default_planner_lexicon()).classify(
            "Can you forecast conversion rate next month?"
        )

        self.assertEqual(intent.scenario_id, "unsupported_forecast")
        self.assertIn("forecast", intent.matched_signals)

    def test_user_lexicon_extends_default_terms(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        with handle:
            json.dump(
                {
                    "version": "user-v1",
                    "scenarios": {
                        "conversion_rate_analysis": {
                            "required_any": [["成交率"]],
                            "optional": ["渠道", "最高"],
                        }
                    },
                },
                handle,
            )

        lexicon = LexiconStore(default_planner_lexicon()).load_user_overrides(Path(handle.name))
        intent = PlannerClassifier(lexicon).classify("哪个渠道成交率最高？")

        self.assertEqual(intent.scenario_id, "conversion_rate_analysis")
        self.assertIn("成交率", intent.matched_signals)

    def test_suggestion_builder_records_pending_user_review(self):
        suggestion = LexiconSuggestionBuilder().from_misclassification(
            question="哪个渠道成交率最高？",
            actual_scenario="unknown",
            expected_scenario="conversion_rate_analysis",
            suggested_terms=["成交率"],
        )

        self.assertEqual(suggestion.status, "pending_review")
        self.assertEqual(suggestion.expected_scenario, "conversion_rate_analysis")
        self.assertEqual(suggestion.suggested_terms, ["成交率"])


if __name__ == "__main__":
    unittest.main()
