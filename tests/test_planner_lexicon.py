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

        self.assertEqual(intent.scenario_id, "metric_analysis")
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
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
        with handle:
            handle.write(
                "scenario_id,match_type,terms,confidence_base\n"
                "metric_analysis,required_any,conversion+rate,0.82\n"
                "metric_analysis,optional,channel|highest,\n"
            )

        lexicon = LexiconStore().load_csv(Path(handle.name))
        intent = PlannerClassifier(lexicon).classify("Which channel has the highest conversion rate?")

        self.assertEqual(intent.scenario_id, "metric_analysis")
        self.assertIn("conversion", intent.matched_signals)
        self.assertIn("rate", intent.matched_signals)

    def test_default_lexicon_classifies_revenue_as_supported_metric_analysis(self):
        intent = PlannerClassifier(default_planner_lexicon()).classify(
            "Which channel has the highest revenue?"
        )

        self.assertEqual(intent.scenario_id, "metric_analysis")
        self.assertIn("revenue", intent.matched_signals)

    def test_default_lexicon_loads_from_config_csv(self):
        lexicon = default_planner_lexicon()

        self.assertTrue(lexicon.version.startswith("csv:"))
        self.assertIn("metric_analysis", lexicon.scenarios)

    def test_suggestion_builder_records_pending_user_review(self):
        suggestion = LexiconSuggestionBuilder().from_misclassification(
            question="哪个渠道成交率最高？",
            actual_scenario="unknown",
            expected_scenario="metric_analysis",
            suggested_terms=["成交率"],
        )

        self.assertEqual(suggestion.status, "pending_review")
        self.assertEqual(suggestion.expected_scenario, "metric_analysis")
        self.assertEqual(suggestion.suggested_terms, ["成交率"])


if __name__ == "__main__":
    unittest.main()
