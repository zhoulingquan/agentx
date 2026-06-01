import tempfile
import unittest
from pathlib import Path

from powerbanana.analysis_request import default_analysis_terms
from powerbanana.blackboard import TaskBlackboard
from powerbanana.models import VocabularySuggestion
from powerbanana.vocabulary import (
    VocabularyApprovalService,
    VocabularySuggestionRepository,
    VocabularySuggestionStore,
    VocabularySuggestionValidator,
)


class VocabularyManagerTests(unittest.TestCase):
    def region_suggestion(self, target_csv: str = "config/analysis_terms.csv", status: str = "pending_user_approval"):
        return VocabularySuggestion(
            target_csv=target_csv,
            kind="group_by",
            value="region",
            terms=["地区", "区域"],
            reason="missing_group_by_term",
            source="fake_llm",
            confidence=0.8,
            status=status,
        )

    def test_blackboard_records_vocabulary_suggestion_entry(self):
        blackboard = TaskBlackboard(question="哪个地区收入最高？")
        suggestion = self.region_suggestion()

        blackboard.record_vocabulary_suggestion(suggestion)

        self.assertEqual(blackboard.vocabulary_suggestions, [suggestion])
        self.assertIn("vocabulary_suggestion_recorded", [event.event_type for event in blackboard.events])
        entry = next(entry for entry in blackboard.entries if entry.entry_type == "vocabulary_suggestion")
        self.assertEqual(entry.payload["value"], "region")
        self.assertEqual(entry.payload["status"], "pending_user_approval")

    def test_validator_accepts_existing_dataset_column_and_new_terms(self):
        suggestion = self.region_suggestion()

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

    def test_repository_saves_pending_suggestion_with_stable_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            repo = VocabularySuggestionRepository(path)

            record = repo.save_pending(self.region_suggestion())

            self.assertEqual(record.suggestion_id, "vocab_000001")
            self.assertEqual(record.status, "pending_user_approval")
            self.assertEqual(record.suggestion.value, "region")
            self.assertTrue(record.created_at.endswith("Z"))
            self.assertTrue(path.exists())
            self.assertEqual(repo.list_records()[0].suggestion.value, "region")

    def test_approval_service_appends_csv_and_marks_record_approved(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            terms_path = Path(tmpdir) / "analysis_terms.csv"
            drafts_dir = Path(tmpdir) / "drafts"
            terms_path.write_text(
                "kind,value,terms,aggregation,required_columns\n"
                "group_by,channel,channel|渠道,,\n",
                encoding="utf-8",
            )
            repo = VocabularySuggestionRepository(store_path)
            repo.save_pending(self.region_suggestion(target_csv=str(terms_path)))

            record = VocabularyApprovalService(repo).approve(
                "vocab_000001",
                terms_path,
                reviewer_note="looks right",
                golden_case_drafts_dir=drafts_dir,
            )

            self.assertEqual(record.status, "approved")
            self.assertEqual(record.reviewer_note, "looks right")
            self.assertEqual(record.validation_status, "passed")
            self.assertIn("analysis_terms_csv_loaded", record.validation_output)
            self.assertTrue(Path(record.golden_case_draft_path).exists())
            self.assertIn("vocab_000001", Path(record.golden_case_draft_path).read_text(encoding="utf-8"))
            self.assertIn("group_by,region,地区|区域,,", terms_path.read_text(encoding="utf-8"))
            self.assertEqual(repo.get_record("vocab_000001").status, "approved")

    def test_approval_service_preview_does_not_mutate_csv_or_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            terms_path = Path(tmpdir) / "analysis_terms.csv"
            terms_path.write_text(
                "kind,value,terms,aggregation,required_columns\n"
                "group_by,channel,channel|渠道,,\n",
                encoding="utf-8",
            )
            original = terms_path.read_text(encoding="utf-8")
            repo = VocabularySuggestionRepository(store_path)
            repo.save_pending(self.region_suggestion(target_csv=str(terms_path)))

            preview = VocabularyApprovalService(repo).preview("vocab_000001")

            self.assertEqual(preview.csv_line, "group_by,region,地区|区域,,")
            self.assertEqual(repo.get_record("vocab_000001").status, "pending_user_approval")
            self.assertEqual(terms_path.read_text(encoding="utf-8"), original)

    def test_approval_service_marks_validation_failed_when_csv_cannot_be_loaded(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            terms_path = Path(tmpdir) / "analysis_terms.csv"
            terms_path.write_text(
                "kind,value,terms,aggregation,required_columns\n"
                "unsupported,bad,bad,,\n",
                encoding="utf-8",
            )
            repo = VocabularySuggestionRepository(store_path)
            repo.save_pending(self.region_suggestion(target_csv=str(terms_path)))

            record = VocabularyApprovalService(repo).approve("vocab_000001", terms_path)

            self.assertEqual(record.status, "approved_validation_failed")
            self.assertEqual(record.validation_status, "failed")
            self.assertTrue(any("Unsupported analysis term kind" in item for item in record.validation_output))

    def test_approval_service_rejects_without_mutating_csv(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = Path(tmpdir) / "vocabulary_suggestions.jsonl"
            terms_path = Path(tmpdir) / "analysis_terms.csv"
            terms_path.write_text(
                "kind,value,terms,aggregation,required_columns\n"
                "group_by,channel,channel|渠道,,\n",
                encoding="utf-8",
            )
            original = terms_path.read_text(encoding="utf-8")
            repo = VocabularySuggestionRepository(store_path)
            repo.save_pending(self.region_suggestion(target_csv=str(terms_path)))

            record = VocabularyApprovalService(repo).reject("vocab_000001", reviewer_note="not needed")

            self.assertEqual(record.status, "rejected")
            self.assertEqual(record.reviewer_note, "not needed")
            self.assertEqual(terms_path.read_text(encoding="utf-8"), original)
            self.assertEqual(repo.get_record("vocab_000001").status, "rejected")

    def test_store_appends_approved_group_by_suggestion_to_csv(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8", newline="")
        with handle:
            handle.write(
                "kind,value,terms,aggregation,required_columns\n"
                "group_by,channel,channel|渠道,,\n"
            )
        path = Path(handle.name)
        suggestion = self.region_suggestion(target_csv=str(path), status="approved")

        VocabularySuggestionStore().append_approved(path, suggestion)

        self.assertIn("group_by,region,地区|区域,,", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
