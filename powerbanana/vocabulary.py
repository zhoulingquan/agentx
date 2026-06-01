from __future__ import annotations

import csv
import io
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .analysis_request import AnalysisTermStore, AnalysisTerms, _contains_term, _normalize
from .models import VocabularySuggestion


DEFAULT_SUGGESTION_STORE_PATH = Path("runs") / "vocabulary_suggestions.jsonl"
DEFAULT_GOLDEN_CASE_DRAFTS_DIR = Path("runs") / "golden_case_drafts"
PENDING_STATUS = "pending_user_approval"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"
APPROVED_VALIDATION_FAILED_STATUS = "approved_validation_failed"


class LLMVocabularyAdvisor(Protocol):
    def suggest(
        self,
        question: str,
        dataset_columns: list[str],
        analysis_terms: AnalysisTerms,
    ) -> VocabularySuggestion | None:
        ...


class NullVocabularyAdvisor:
    def suggest(
        self,
        question: str,
        dataset_columns: list[str],
        analysis_terms: AnalysisTerms,
    ) -> VocabularySuggestion | None:
        return None


@dataclass(frozen=True)
class VocabularySuggestionValidation:
    passed: bool
    failure_reasons: list[str]


@dataclass(frozen=True)
class VocabularySuggestionRecord:
    suggestion_id: str
    status: str
    created_at: str
    updated_at: str
    suggestion: VocabularySuggestion
    reviewer_note: str = ""
    validation_status: str = ""
    validation_output: list[str] = field(default_factory=list)
    golden_case_draft_path: str = ""


@dataclass(frozen=True)
class VocabularyApprovalPreview:
    suggestion_id: str
    csv_line: str
    suggestion: VocabularySuggestion


@dataclass(frozen=True)
class VocabularyApprovalValidation:
    passed: bool
    output: list[str]


class VocabularySuggestionValidator:
    def __init__(self, analysis_terms: AnalysisTerms) -> None:
        self.analysis_terms = analysis_terms

    def validate(self, suggestion: VocabularySuggestion, dataset_columns: list[str]) -> VocabularySuggestionValidation:
        failures: list[str] = []
        if suggestion.target_csv != "config/analysis_terms.csv" and not suggestion.target_csv.endswith("analysis_terms.csv"):
            failures.append("unsupported_target_csv")
        if suggestion.kind != "group_by":
            failures.append("unsupported_suggestion_kind")
        if suggestion.value not in dataset_columns:
            failures.append("suggested_value_not_in_dataset_columns")
        if not suggestion.terms:
            failures.append("missing_suggested_terms")
        if self._terms_already_active(suggestion.terms):
            failures.append("suggested_terms_already_active")
        return VocabularySuggestionValidation(
            passed=not failures,
            failure_reasons=failures,
        )

    def _terms_already_active(self, terms: list[str]) -> bool:
        active_terms = []
        for term in [*self.analysis_terms.metrics, *self.analysis_terms.group_by, *self.analysis_terms.rank_directions]:
            active_terms.extend(term.terms)
        normalized_active = {_normalize(term) for term in active_terms}
        return any(_normalize(term) in normalized_active for term in terms)


class VocabularySuggestionStore:
    def csv_row(self, suggestion: VocabularySuggestion) -> list[str]:
        return [suggestion.kind, suggestion.value, "|".join(suggestion.terms), "", ""]

    def csv_line(self, suggestion: VocabularySuggestion) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(self.csv_row(suggestion))
        return buffer.getvalue().strip()

    def append_approved(self, path: Path, suggestion: VocabularySuggestion) -> None:
        if suggestion.status != "approved":
            raise ValueError("Only approved vocabulary suggestions can be appended.")
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.csv_row(suggestion))


class VocabularySuggestionRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or DEFAULT_SUGGESTION_STORE_PATH

    def save_pending(self, suggestion: VocabularySuggestion) -> VocabularySuggestionRecord:
        records = self.list_records()
        now = _utc_now()
        pending_suggestion = replace(suggestion, status=PENDING_STATUS)
        record = VocabularySuggestionRecord(
            suggestion_id=self._next_suggestion_id(records),
            status=PENDING_STATUS,
            created_at=now,
            updated_at=now,
            suggestion=pending_suggestion,
        )
        self._write_records([*records, record])
        return record

    def list_records(self, status: str | None = None) -> list[VocabularySuggestionRecord]:
        if not self.path.exists():
            return []
        records: list[VocabularySuggestionRecord] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                record = _record_from_json(json.loads(stripped))
                if status is None or record.status == status:
                    records.append(record)
        return records

    def get_record(self, suggestion_id: str) -> VocabularySuggestionRecord:
        for record in self.list_records():
            if record.suggestion_id == suggestion_id:
                return record
        raise KeyError(f"Unknown vocabulary suggestion id: {suggestion_id}")

    def mark_approved(
        self,
        suggestion_id: str,
        reviewer_note: str = "",
        status: str = APPROVED_STATUS,
        validation_status: str = "",
        validation_output: list[str] | None = None,
        golden_case_draft_path: str = "",
    ) -> VocabularySuggestionRecord:
        record = self.get_record(suggestion_id)
        if record.status != PENDING_STATUS:
            raise ValueError(f"Vocabulary suggestion {suggestion_id} is already {record.status}.")
        return self._replace_record_with_metadata(
            suggestion_id,
            status=status,
            reviewer_note=reviewer_note,
            validation_status=validation_status,
            validation_output=validation_output or [],
            golden_case_draft_path=golden_case_draft_path,
        )

    def mark_rejected(self, suggestion_id: str, reviewer_note: str = "") -> VocabularySuggestionRecord:
        record = self.get_record(suggestion_id)
        if record.status != PENDING_STATUS:
            raise ValueError(f"Vocabulary suggestion {suggestion_id} is already {record.status}.")
        return self._replace_record_with_metadata(
            suggestion_id,
            status=REJECTED_STATUS,
            reviewer_note=reviewer_note,
            validation_status="",
            validation_output=[],
            golden_case_draft_path="",
        )

    def _replace_record_with_metadata(
        self,
        suggestion_id: str,
        status: str,
        reviewer_note: str,
        validation_status: str,
        validation_output: list[str],
        golden_case_draft_path: str,
    ) -> VocabularySuggestionRecord:
        records = self.list_records()
        updated_records: list[VocabularySuggestionRecord] = []
        updated_record: VocabularySuggestionRecord | None = None
        for record in records:
            if record.suggestion_id != suggestion_id:
                updated_records.append(record)
                continue
            updated_record = replace(
                record,
                status=status,
                updated_at=_utc_now(),
                reviewer_note=reviewer_note,
                validation_status=validation_status,
                validation_output=validation_output,
                golden_case_draft_path=golden_case_draft_path,
                suggestion=replace(record.suggestion, status=status),
            )
            updated_records.append(updated_record)
        if updated_record is None:
            raise KeyError(f"Unknown vocabulary suggestion id: {suggestion_id}")
        self._write_records(updated_records)
        return updated_record

    def _write_records(self, records: list[VocabularySuggestionRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            for record in records:
                handle.write(json.dumps(_record_to_json(record), ensure_ascii=False, sort_keys=True))
                handle.write("\n")

    def _next_suggestion_id(self, records: list[VocabularySuggestionRecord]) -> str:
        max_index = 0
        for record in records:
            prefix, _, suffix = record.suggestion_id.partition("_")
            if prefix == "vocab" and suffix.isdigit():
                max_index = max(max_index, int(suffix))
        return f"vocab_{max_index + 1:06d}"


class VocabularyApprovalService:
    def __init__(
        self,
        repository: VocabularySuggestionRepository,
        suggestion_store: VocabularySuggestionStore | None = None,
    ) -> None:
        self.repository = repository
        self.suggestion_store = suggestion_store or VocabularySuggestionStore()

    def preview(self, suggestion_id: str) -> VocabularyApprovalPreview:
        record = self.repository.get_record(suggestion_id)
        if record.status != PENDING_STATUS:
            raise ValueError(f"Vocabulary suggestion {suggestion_id} is already {record.status}.")
        return VocabularyApprovalPreview(
            suggestion_id=record.suggestion_id,
            csv_line=self.suggestion_store.csv_line(record.suggestion),
            suggestion=record.suggestion,
        )

    def approve(
        self,
        suggestion_id: str,
        analysis_terms_path: Path,
        reviewer_note: str = "",
        golden_case_drafts_dir: Path | None = None,
    ) -> VocabularySuggestionRecord:
        record = self.repository.get_record(suggestion_id)
        if record.status != PENDING_STATUS:
            raise ValueError(f"Vocabulary suggestion {suggestion_id} is already {record.status}.")
        self.suggestion_store.append_approved(
            analysis_terms_path,
            replace(record.suggestion, status=APPROVED_STATUS),
        )
        validation = self._validate_approved_term(analysis_terms_path, record.suggestion)
        draft_path = self._write_golden_case_draft(record, golden_case_drafts_dir or DEFAULT_GOLDEN_CASE_DRAFTS_DIR)
        status = APPROVED_STATUS if validation.passed else APPROVED_VALIDATION_FAILED_STATUS
        return self.repository.mark_approved(
            suggestion_id,
            reviewer_note=reviewer_note,
            status=status,
            validation_status="passed" if validation.passed else "failed",
            validation_output=validation.output,
            golden_case_draft_path=str(draft_path),
        )

    def reject(self, suggestion_id: str, reviewer_note: str = "") -> VocabularySuggestionRecord:
        return self.repository.mark_rejected(suggestion_id, reviewer_note=reviewer_note)

    def _validate_approved_term(self, analysis_terms_path: Path, suggestion: VocabularySuggestion) -> VocabularyApprovalValidation:
        output: list[str] = []
        try:
            analysis_terms = AnalysisTermStore().load_csv(analysis_terms_path)
            output.append("analysis_terms_csv_loaded")
        except Exception as exc:
            return VocabularyApprovalValidation(False, [f"analysis_terms_csv_load_failed: {exc}"])

        term_groups = {
            "metric": analysis_terms.metrics,
            "group_by": analysis_terms.group_by,
            "rank_direction": analysis_terms.rank_directions,
        }
        candidates = term_groups.get(suggestion.kind)
        if candidates is None:
            return VocabularyApprovalValidation(False, [*output, f"unsupported_suggestion_kind: {suggestion.kind}"])

        active = next((term for term in candidates if term.value == suggestion.value), None)
        if active is None:
            return VocabularyApprovalValidation(False, [*output, f"approved_value_not_active: {suggestion.value}"])

        missing_terms = [term for term in suggestion.terms if term not in active.terms]
        if missing_terms:
            return VocabularyApprovalValidation(False, [*output, f"approved_terms_not_active: {'|'.join(missing_terms)}"])

        output.append(f"approved_value_active: {suggestion.kind}={suggestion.value}")
        output.append(f"approved_terms_active: {'|'.join(suggestion.terms)}")
        return VocabularyApprovalValidation(True, output)

    def _write_golden_case_draft(self, record: VocabularySuggestionRecord, drafts_dir: Path) -> Path:
        suggestion = record.suggestion
        drafts_dir.mkdir(parents=True, exist_ok=True)
        path = drafts_dir / f"{record.suggestion_id}_{suggestion.kind}_{suggestion.value}.json"
        payload = {
            "draft_type": "vocabulary_approval_golden_case",
            "suggestion_id": record.suggestion_id,
            "target_csv": suggestion.target_csv,
            "suggestion": asdict(suggestion),
            "planner_case_draft": {
                "case_id": f"{suggestion.value}_{suggestion.kind}_metric_analysis",
                "question": f"Replace this with a real user question using one of: {'|'.join(suggestion.terms)}",
                "expected_scenario": "metric_analysis",
                "expected_min_confidence": 0.8,
                "expected_matched_signals_contains": suggestion.terms[:1],
            },
            "end_to_end_case_draft": {
                "case_id": f"{suggestion.value}_{suggestion.kind}_metric_question",
                "dataset_columns_must_include": [suggestion.value],
                "expected_group_by": suggestion.value,
                "promotion_note": "Review the draft, add a synthetic CSV fixture, set expected answer fields, then promote into evals/golden_cases.",
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path


class VocabularyManager:
    def __init__(
        self,
        advisor: LLMVocabularyAdvisor | None,
        analysis_terms: AnalysisTerms,
        suggestion_repository: VocabularySuggestionRepository | None = None,
    ) -> None:
        self.advisor = advisor or NullVocabularyAdvisor()
        self.analysis_terms = analysis_terms
        self.validator = VocabularySuggestionValidator(analysis_terms)
        self.suggestion_repository = suggestion_repository or VocabularySuggestionRepository()

    def suggest(self, question: str, dataset_columns: list[str]) -> tuple[VocabularySuggestion | None, VocabularySuggestionValidation]:
        suggestion = self.advisor.suggest(question, dataset_columns, self.analysis_terms)
        if suggestion is None:
            return None, VocabularySuggestionValidation(False, ["no_vocabulary_suggestion"])
        validation = self.validator.validate(suggestion, dataset_columns)
        return suggestion if validation.passed else None, validation

    def record_pending(self, suggestion: VocabularySuggestion) -> VocabularySuggestionRecord:
        return self.suggestion_repository.save_pending(suggestion)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _record_to_json(record: VocabularySuggestionRecord) -> dict[str, object]:
    return {
        "suggestion_id": record.suggestion_id,
        "status": record.status,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
        "reviewer_note": record.reviewer_note,
        "validation_status": record.validation_status,
        "validation_output": record.validation_output,
        "golden_case_draft_path": record.golden_case_draft_path,
        "suggestion": asdict(record.suggestion),
    }


def _record_from_json(data: dict[str, object]) -> VocabularySuggestionRecord:
    suggestion_data = data.get("suggestion")
    if not isinstance(suggestion_data, dict):
        raise ValueError("Vocabulary suggestion record is missing suggestion data.")
    return VocabularySuggestionRecord(
        suggestion_id=str(data.get("suggestion_id", "")),
        status=str(data.get("status", PENDING_STATUS)),
        created_at=str(data.get("created_at", "")),
        updated_at=str(data.get("updated_at", "")),
        reviewer_note=str(data.get("reviewer_note", "")),
        validation_status=str(data.get("validation_status", "")),
        validation_output=_string_list(data.get("validation_output")),
        golden_case_draft_path=str(data.get("golden_case_draft_path", "")),
        suggestion=VocabularySuggestion(**suggestion_data),
    )


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
