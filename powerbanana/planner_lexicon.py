from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .models import PlannerIntent


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
    def __init__(self, base_lexicon: PlannerLexicon) -> None:
        self.base_lexicon = base_lexicon

    def load_user_overrides(self, path: Path) -> PlannerLexicon:
        payload = json.loads(path.read_text(encoding="utf-8"))
        scenarios = dict(self.base_lexicon.scenarios)
        for scenario_id, rule_payload in payload.get("scenarios", {}).items():
            base_rule = scenarios.get(scenario_id, ScenarioRule(scenario_id=scenario_id, required_any=[]))
            scenarios[scenario_id] = _merge_rule(base_rule, rule_payload)
        version = f"{self.base_lexicon.version}+{payload.get('version', 'user')}"
        return PlannerLexicon(version=version, scenarios=scenarios)


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


def default_planner_lexicon() -> PlannerLexicon:
    return PlannerLexicon(
        version="builtin-v1",
        scenarios={
            "unsupported_forecast": ScenarioRule(
                scenario_id="unsupported_forecast",
                required_any=[["forecast"], ["predict"], ["预测"], ["预估"]],
                optional=["next month", "sales", "revenue", "conversion rate"],
                confidence_base=0.9,
                warnings=["unsupported_capability"],
            ),
            "conversion_rate_analysis": ScenarioRule(
                scenario_id="conversion_rate_analysis",
                required_any=[["conversion", "rate"], ["conversion_rate"], ["转化率"], ["成交率"]],
                optional=["highest", "best", "channel", "渠道", "最高"],
                negative=["forecast", "predict", "预测", "预估", "join", "merge"],
                confidence_base=0.8,
            ),
            "unsupported_revenue": ScenarioRule(
                scenario_id="unsupported_revenue",
                required_any=[["revenue"], ["sales"], ["收入"], ["营收"], ["gmv"]],
                optional=["highest", "best", "channel", "渠道"],
                confidence_base=0.85,
                warnings=["unsupported_capability"],
            ),
            "ambiguous_metric": ScenarioRule(
                scenario_id="ambiguous_metric",
                required_any=[["best"], ["perform"], ["performs"], ["表现最好"], ["最好"]],
                optional=["channel", "渠道"],
                negative=["conversion", "rate", "revenue", "orders", "visits", "转化率", "成交率", "收入", "营收"],
                confidence_base=0.7,
                warnings=["missing_metric"],
            ),
        },
    )


def _merge_rule(base_rule: ScenarioRule, payload: dict[str, Any]) -> ScenarioRule:
    return replace(
        base_rule,
        required_any=[*base_rule.required_any, *payload.get("required_any", [])],
        optional=[*base_rule.optional, *payload.get("optional", [])],
        negative=[*base_rule.negative, *payload.get("negative", [])],
        warnings=[*base_rule.warnings, *payload.get("warnings", [])],
        confidence_base=payload.get("confidence_base", base_rule.confidence_base),
    )


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
