import tempfile
import unittest
from pathlib import Path

from powerbanana.analysis_request import default_analysis_terms
from powerbanana.blackboard import TaskBlackboard
from powerbanana.models import VocabularySuggestion
from powerbanana.vocabulary import VocabularySuggestionStore, VocabularySuggestionValidator


class VocabularyManagerTests(unittest.TestCase):
    def test_blackboard_records_vocabulary_suggestion_entry(self):
        blackboard = TaskBlackboard(question="哪个地区收入最高？")
        suggestion = VocabularySuggestion(
            target_csv="config/analysis_terms.csv",
            kind="group_by",
            value="region",
            terms=["地区", "区域"],
            reason="missing_group_by_term",
            source="fake_llm",
            confidence=0.8,
        )

        blackboard.record_vocabulary_suggestion(suggestion)

        self.assertEqual(blackboard.vocabulary_suggestions, [suggestion])
        self.assertIn("vocabulary_suggestion_recorded", [event.event_type for event in blackboard.events])
        entry = next(entry for entry in blackboard.entries if entry.entry_type == "vocabulary_suggestion")
        self.assertEqual(entry.payload["value"], "region")
        self.assertEqual(entry.payload["status"], "pending_user_approval")

    def test_validator_accepts_existing_dataset_column_and_new_terms(self):
        suggestion = VocabularySuggestion(
            target_csv="config/analysis_terms.csv",
            kind="group_by",
            value="region",
            terms=["地区", "区域"],
            reason="missing_group_by_term",
            source="fake_llm",
            confidence=0.8,
        )

        result = VocabularySuggestionValidator(default_analysis_terms()).validate(
            suggestion,
            dataset_columns=["region", "revenue"],
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.failure_reasons, [])

    def test_validator_rejects_hallucinated_column(self):
        suggestion = VocabularySuggestion(
            target_csv="config/analysis_terms.csv",
            kind="group_by",
            value="country",
            terms=["国家"],
            reason="missing_group_by_term",
            source="fake_llm",
            confidence=0.8,
        )

        result = VocabularySuggestionValidator(default_analysis_terms()).validate(
            suggestion,
            dataset_columns=["region", "revenue"],
        )

        self.assertFalse(result.passed)
        self.assertIn("suggested_value_not_in_dataset_columns", result.failure_reasons)

    def test_store_appends_approved_group_by_suggestion_to_csv(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
        with handle:
            handle.write(
                "kind,value,terms,aggregation,required_columns\n"
                "group_by,channel,channel|渠道,,\n"
            )
        path = Path(handle.name)
        suggestion = VocabularySuggestion(
            target_csv=str(path),
            kind="group_by",
            value="region",
            terms=["地区", "区域"],
            reason="missing_group_by_term",
            source="fake_llm",
            confidence=0.8,
            status="approved",
        )

        VocabularySuggestionStore().append_approved(path, suggestion)

        self.assertIn("group_by,region,地区|区域,,", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
