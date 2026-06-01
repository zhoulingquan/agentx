from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .analysis_request import AnalysisTerms, _contains_term, _normalize
from .models import VocabularySuggestion


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


class VocabularyManager:
    def __init__(self, advisor: LLMVocabularyAdvisor | None, analysis_terms: AnalysisTerms) -> None:
        self.advisor = advisor or NullVocabularyAdvisor()
        self.analysis_terms = analysis_terms
        self.validator = VocabularySuggestionValidator(analysis_terms)

    def suggest(self, question: str, dataset_columns: list[str]) -> tuple[VocabularySuggestion | None, VocabularySuggestionValidation]:
        suggestion = self.advisor.suggest(question, dataset_columns, self.analysis_terms)
        if suggestion is None:
            return None, VocabularySuggestionValidation(False, ["no_vocabulary_suggestion"])
        validation = self.validator.validate(suggestion, dataset_columns)
        return suggestion if validation.passed else None, validation
