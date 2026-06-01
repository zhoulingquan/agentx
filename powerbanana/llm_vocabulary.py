from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .analysis_request import AnalysisTerm, AnalysisTerms
from .models import VocabularySuggestion
from .vocabulary import PENDING_STATUS


VOCABULARY_SUGGESTION_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["should_suggest", "suggestion"],
    "properties": {
        "should_suggest": {
            "type": "boolean",
            "description": "Whether a new analysis vocabulary row should be proposed.",
        },
        "suggestion": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "value", "terms", "reason", "confidence"],
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["group_by"],
                    "description": "Only group_by suggestions are currently supported.",
                },
                "value": {
                    "type": "string",
                    "description": "Dataset column that should become a group_by value.",
                },
                "terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "User-facing synonyms to append into analysis_terms.csv.",
                },
                "reason": {
                    "type": "string",
                    "description": "Short reason explaining why the term is useful.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence from 0.0 to 1.0.",
                },
            },
        },
    },
}


SYSTEM_PROMPT = (
    "You are PowerBanana's vocabulary advisor. Return JSON only. "
    "Suggest at most one missing group_by vocabulary row for config/analysis_terms.csv. "
    "Only suggest a value that exactly matches one of the dataset columns. "
    "Do not suggest terms that are already active. "
    "If no safe suggestion exists, set should_suggest to false."
)


class LLMJsonClient(Protocol):
    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class JsonLLMVocabularyAdvisor:
    client: LLMJsonClient
    model: str
    temperature: float = 0.0
    max_tokens: int = 500
    provider: str = "openai_compatible"
    source_name: str = "llm_json_advisor"

    def suggest(
        self,
        question: str,
        dataset_columns: list[str],
        analysis_terms: AnalysisTerms,
    ) -> VocabularySuggestion | None:
        try:
            payload = self.client.complete_json(
                system_prompt=SYSTEM_PROMPT,
                user_payload=_build_user_payload(question, dataset_columns, analysis_terms),
                schema=VOCABULARY_SUGGESTION_RESPONSE_SCHEMA,
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception:
            return None
        return self._suggestion_from_payload(payload)

    def _suggestion_from_payload(self, payload: dict[str, Any]) -> VocabularySuggestion | None:
        if payload.get("should_suggest") is not True:
            return None
        raw_suggestion = payload.get("suggestion")
        if not isinstance(raw_suggestion, dict):
            return None

        kind = _coerce_string(raw_suggestion.get("kind"))
        value = _coerce_string(raw_suggestion.get("value"))
        terms = _coerce_terms(raw_suggestion.get("terms"))
        reason = _coerce_string(raw_suggestion.get("reason")) or "llm_vocabulary_suggestion"
        confidence = _coerce_confidence(raw_suggestion.get("confidence"))
        target_csv = _coerce_string(raw_suggestion.get("target_csv")) or "config/analysis_terms.csv"
        source = _coerce_string(raw_suggestion.get("source")) or self.source_name

        if not kind or not value or not terms:
            return None
        return VocabularySuggestion(
            target_csv=target_csv,
            kind=kind,
            value=value,
            terms=terms,
            reason=reason,
            source=source,
            confidence=confidence,
            status=PENDING_STATUS,
        )


class OpenAIResponsesJsonClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 30.0,
        urlopen: Callable[..., Any] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OpenAIResponsesJsonClient requires an API key.")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.urlopen = urlopen or urllib.request.urlopen

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        schema: dict[str, Any],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        body = {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "powerbanana_vocabulary_suggestion",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        request = urllib.request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with self.urlopen(request, timeout=self.timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        output_text = _extract_response_text(response_payload)
        if not output_text:
            raise ValueError("OpenAI response did not contain JSON output text.")
        parsed = json.loads(output_text)
        if not isinstance(parsed, dict):
            raise ValueError("OpenAI JSON output must be an object.")
        return parsed


def _build_user_payload(question: str, dataset_columns: list[str], analysis_terms: AnalysisTerms) -> dict[str, Any]:
    return {
        "question": question,
        "dataset_columns": dataset_columns,
        "active_analysis_terms": {
            "metrics": [_term_payload(term) for term in analysis_terms.metrics],
            "group_by": [_term_payload(term) for term in analysis_terms.group_by],
            "rank_directions": [_term_payload(term) for term in analysis_terms.rank_directions],
        },
        "target_csv": "config/analysis_terms.csv",
        "allowed_kind": "group_by",
    }


def _term_payload(term: AnalysisTerm) -> dict[str, Any]:
    return {
        "value": term.value,
        "terms": term.terms,
        "aggregation": term.aggregation,
        "required_columns": term.required_columns,
    }


def _extract_response_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str):
        return output_text

    output = payload.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if isinstance(text, str) and content_item.get("type") in {"output_text", "text"}:
                    return text

    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return str(message["content"])
    return ""


def _coerce_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_terms(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    terms: list[str] = []
    for item in value:
        term = _coerce_string(item)
        if term and term not in terms:
            terms.append(term)
    return terms


def _coerce_confidence(value: object) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))
