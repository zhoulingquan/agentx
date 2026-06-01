from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from .analysis_request import AnalysisTerms, _contains_term, _normalize
from .models import VocabularySuggestion


DEFAULT_SUGGESTION_STORE_PATH = Path("runs") / "vocabulary_suggestions.jsonl"
PENDING_STATUS = "pending_user_approval"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"


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
    def append_approved(self, path: Path, suggestion: VocabularySuggestion) -> None:
        if suggestion.status != "approved":
            raise ValueError("Only approved vocabulary suggestions can be appended.")
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([suggestion.kind, suggestion.value, "|".join(suggestion.terms), "", ""])


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

    def mark_approved(self, suggestion_id: str, reviewer_note: str = "") -> VocabularySuggestionRecord:
        record = self.get_record(suggestion_id)
        if record.status != PENDING_STATUS:
            raise ValueError(f"Vocabulary suggestion {suggestion_id} is already {record.status}.")
        return self._replace_record(
            suggestion_id,
            status=APPROVED_STATUS,
            reviewer_note=reviewer_note,
        )

    def mark_rejected(self, suggestion_id: str, reviewer_note: str = "") -> VocabularySuggestionRecord:
        record = self.get_record(suggestion_id)
        if record.status != PENDING_STATUS:
            raise ValueError(f"Vocabulary suggestion {suggestion_id} is already {record.status}.")
        return self._replace_record(
            suggestion_id,
            status=REJECTED_STATUS,
            reviewer_note=reviewer_note,
        )

    def _replace_record(self, suggestion_id: str, status: str, reviewer_note: str) -> VocabularySuggestionRecord:
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

    def approve(self, suggestion_id: str, analysis_terms_path: Path, reviewer_note: str = "") -> VocabularySuggestionRecord:
        record = self.repository.get_record(suggestion_id)
        if record.status != PENDING_STATUS:
            raise ValueError(f"Vocabulary suggestion {suggestion_id} is already {record.status}.")
        self.suggestion_store.append_approved(
            analysis_terms_path,
            replace(record.suggestion, status=APPROVED_STATUS),
        )
        return self.repository.mark_approved(suggestion_id, reviewer_note=reviewer_note)

    def reject(self, suggestion_id: str, reviewer_note: str = "") -> VocabularySuggestionRecord:
        return self.repository.mark_rejected(suggestion_id, reviewer_note=reviewer_note)


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
        suggestion=VocabularySuggestion(**suggestion_data),
    )
