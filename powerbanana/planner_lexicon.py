from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import PlannerIntent

DEFAULT_LEXICON_PATH = Path(__file__).resolve().parent.parent / "config" / "planner_lexicon.csv"


@dataclass(frozen=True)
class ScenarioRule:
    scenario_id: str
    required_any: list[list[str]]
    optional: list[str] = field(default_factory=list)
    negative: list[str] = field(default_factory=list)
    confidence_base: float = 0.5
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PlannerLexicon:
    version: str
    scenarios: dict[str, ScenarioRule]


@dataclass(frozen=True)
class LexiconSuggestion:
    question: str
    actual_scenario: str
    expected_scenario: str
    suggested_terms: list[str]
    status: str = "pending_review"
    reason: str = "planner_misclassification"


class PlannerClassifier:
    def __init__(self, lexicon: PlannerLexicon) -> None:
        self.lexicon = lexicon

    def classify(self, question: str) -> PlannerIntent:
        normalized_question = _normalize(question)
        matches = [
            intent
            for rule in self.lexicon.scenarios.values()
            if (intent := self._match_rule(rule, normalized_question)) is not None
        ]
        if not matches:
            return PlannerIntent(
                scenario_id="unknown",
                confidence=0.2,
                warnings=["unknown_scenario"],
            )
        return sorted(matches, key=lambda intent: intent.confidence, reverse=True)[0]

    def _match_rule(self, rule: ScenarioRule, normalized_question: str) -> PlannerIntent | None:
        if _matched_terms(rule.negative, normalized_question):
            return None

        matched_group: list[str] = []
        for group in rule.required_any:
            if all(_contains_term(term, normalized_question) for term in group):
                matched_group = group
                break
        if not matched_group:
            return None

        optional_matches = _matched_terms(rule.optional, normalized_question)
        confidence = min(0.99, rule.confidence_base + len(optional_matches) * 0.03)
        return PlannerIntent(
            scenario_id=rule.scenario_id,
            confidence=confidence,
            matched_signals=[*matched_group, *optional_matches],
            warnings=rule.warnings,
        )


class LexiconStore:
    def load_csv(self, path: Path) -> PlannerLexicon:
        scenarios: dict[str, ScenarioRule] = {}
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                scenario_id = row.get("scenario_id", "").strip()
                match_type = row.get("match_type", "").strip()
                terms = row.get("terms", "").strip()
                if not scenario_id or not match_type or not terms:
                    continue
                base_rule = scenarios.get(scenario_id, ScenarioRule(scenario_id=scenario_id, required_any=[]))
                scenarios[scenario_id] = self._append_row(base_rule, match_type, terms, row.get("confidence_base", ""))
        return PlannerLexicon(version=f"csv:{path.as_posix()}", scenarios=scenarios)

    def _append_row(self, rule: ScenarioRule, match_type: str, terms: str, confidence_base: str | None) -> ScenarioRule:
        confidence = _parse_confidence(confidence_base, rule.confidence_base)
        if match_type == "required_any":
            return ScenarioRule(
                scenario_id=rule.scenario_id,
                required_any=[*rule.required_any, *_parse_required_groups(terms)],
                optional=rule.optional,
                negative=rule.negative,
                confidence_base=confidence,
                warnings=rule.warnings,
            )
        if match_type == "optional":
            return ScenarioRule(
                scenario_id=rule.scenario_id,
                required_any=rule.required_any,
                optional=[*rule.optional, *_split_terms(terms)],
                negative=rule.negative,
                confidence_base=confidence,
                warnings=rule.warnings,
            )
        if match_type == "negative":
            return ScenarioRule(
                scenario_id=rule.scenario_id,
                required_any=rule.required_any,
                optional=rule.optional,
                negative=[*rule.negative, *_split_terms(terms)],
                confidence_base=confidence,
                warnings=rule.warnings,
            )
        if match_type == "warnings":
            return ScenarioRule(
                scenario_id=rule.scenario_id,
                required_any=rule.required_any,
                optional=rule.optional,
                negative=rule.negative,
                confidence_base=confidence,
                warnings=[*rule.warnings, *_split_terms(terms)],
            )
        raise ValueError(f"Unsupported planner lexicon match_type: {match_type}")


class LexiconSuggestionBuilder:
    def from_misclassification(
        self,
        question: str,
        actual_scenario: str,
        expected_scenario: str,
        suggested_terms: list[str],
    ) -> LexiconSuggestion:
        return LexiconSuggestion(
            question=question,
            actual_scenario=actual_scenario,
            expected_scenario=expected_scenario,
            suggested_terms=suggested_terms,
        )


def default_planner_lexicon(path: Path | None = None) -> PlannerLexicon:
    return LexiconStore().load_csv(path or DEFAULT_LEXICON_PATH)


def _parse_confidence(value: str | None, fallback: float) -> float:
    if value is None or not str(value).strip():
        return fallback
    return float(str(value).strip())


def _parse_required_groups(terms: str) -> list[list[str]]:
    groups = []
    for group in _split_terms(terms):
        members = [term.strip() for term in group.split("+") if term.strip()]
        if members:
            groups.append(members)
    return groups


def _split_terms(terms: str) -> list[str]:
    return [term.strip() for term in terms.split("|") if term.strip()]


def _normalize(text: str) -> str:
    lowered = text.lower()
    spaced = re.sub(r"[_\W]+", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", spaced).strip()


def _contains_term(term: str, normalized_question: str) -> bool:
    normalized_term = _normalize(term)
    if not normalized_term:
        return False
    return normalized_term in normalized_question


def _matched_terms(terms: list[str], normalized_question: str) -> list[str]:
    return [term for term in terms if _contains_term(term, normalized_question)]
