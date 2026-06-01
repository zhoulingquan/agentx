from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import AnalysisRequest


DEFAULT_ANALYSIS_TERMS_PATH = Path(__file__).resolve().parent.parent / "config" / "analysis_terms.csv"


@dataclass(frozen=True)
class AnalysisTerm:
    kind: str
    value: str
    terms: list[str]
    aggregation: str = ""
    required_columns: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisTerms:
    version: str
    metrics: list[AnalysisTerm]
    group_by: list[AnalysisTerm]
    rank_directions: list[AnalysisTerm]


class AnalysisTermStore:
    def load_csv(self, path: Path) -> AnalysisTerms:
        metrics: list[AnalysisTerm] = []
        group_by: list[AnalysisTerm] = []
        rank_directions: list[AnalysisTerm] = []
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                term = AnalysisTerm(
                    kind=row.get("kind", "").strip(),
                    value=row.get("value", "").strip(),
                    terms=_split_terms(row.get("terms", "")),
                    aggregation=row.get("aggregation", "").strip(),
                    required_columns=_split_terms(row.get("required_columns", "")),
                )
                if not term.kind or not term.value or not term.terms:
                    continue
                if term.kind == "metric":
                    metrics.append(term)
                elif term.kind == "group_by":
                    group_by.append(term)
                elif term.kind == "rank_direction":
                    rank_directions.append(term)
                else:
                    raise ValueError(f"Unsupported analysis term kind: {term.kind}")
        return AnalysisTerms(
            version=f"csv:{path.as_posix()}",
            metrics=metrics,
            group_by=group_by,
            rank_directions=rank_directions,
        )


class AnalysisRequestParser:
    def __init__(self, terms: AnalysisTerms) -> None:
        self.terms = terms

    def parse(self, question: str, allow_default_group_by: bool = True) -> AnalysisRequest:
        request = self.parse_optional(question, allow_default_group_by=allow_default_group_by)
        if request is None:
            raise ValueError("Could not parse analysis request from question.")
        return request

    def parse_optional(self, question: str, allow_default_group_by: bool = True) -> AnalysisRequest | None:
        normalized_question = _normalize(question)
        metric = _first_match(self.terms.metrics, normalized_question)
        if metric is None:
            return None
        group_by = _first_match(self.terms.group_by, normalized_question)
        if group_by is None and allow_default_group_by:
            group_by = _single_default(self.terms.group_by)
        if group_by is None:
            return None
        rank_direction = _first_match(self.terms.rank_directions, normalized_question)
        rank_value = rank_direction.value if rank_direction else "highest"
        return AnalysisRequest(
            metric=metric.value,
            group_by=group_by.value,
            aggregation=metric.aggregation or "sum",
            rank_direction=rank_value,
            required_columns=metric.required_columns or [group_by.value, metric.value],
        )


def default_analysis_terms(path: Path | None = None) -> AnalysisTerms:
    return AnalysisTermStore().load_csv(path or DEFAULT_ANALYSIS_TERMS_PATH)


def _first_match(terms: list[AnalysisTerm], normalized_question: str) -> AnalysisTerm | None:
    for term in terms:
        if any(_contains_term(candidate, normalized_question) for candidate in term.terms):
            return term
    return None


def _single_default(terms: list[AnalysisTerm]) -> AnalysisTerm | None:
    if len(terms) == 1:
        return terms[0]
    return None


def _split_terms(value: str | None) -> list[str]:
    return [term.strip() for term in str(value or "").split("|") if term.strip()]


def _normalize(text: str) -> str:
    lowered = text.lower()
    spaced = re.sub(r"[_\W]+", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", spaced).strip()


def _contains_term(term: str, normalized_question: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False
    return normalized_term in normalized_question
