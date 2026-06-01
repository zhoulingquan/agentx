from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evals import PlannerGoldenCaseRunner
from .planner import DeterministicDataFilePlanner


PLACEHOLDER_QUESTION_PREFIX = "Replace this with a real user question"


@dataclass(frozen=True)
class GoldenPromotionResult:
    case_id: str
    case_path: Path
    validation_passed: bool
    validation_output: list[str]


class GoldenCasePromoter:
    def __init__(self, planner: DeterministicDataFilePlanner | None = None) -> None:
        self.planner = planner or DeterministicDataFilePlanner()

    def promote_planner_case(
        self,
        draft_path: Path,
        planner_cases_dir: Path,
        question: str | None = None,
        case_id: str | None = None,
        matched_signals: list[str] | None = None,
        expected_metric: str | None = None,
        overwrite: bool = False,
    ) -> GoldenPromotionResult:
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        suggestion = _require_dict(draft.get("suggestion"), "suggestion")
        planner_draft = _require_dict(draft.get("planner_case_draft"), "planner_case_draft")
        final_question = (question or str(planner_draft.get("question", ""))).strip()
        if not final_question or final_question.startswith(PLACEHOLDER_QUESTION_PREFIX):
            raise ValueError("Golden case promotion requires a real question. Pass --question or edit the draft first.")

        final_case_id = _safe_case_id(case_id or str(planner_draft.get("case_id") or f"{suggestion['value']}_metric_analysis"))
        case_data = {
            "case_id": final_case_id,
            "question": final_question,
            "expected_scenario": str(planner_draft.get("expected_scenario", "metric_analysis")),
            "expected_min_confidence": float(planner_draft.get("expected_min_confidence", 0.8)),
            "expected_analysis_request": {
                str(suggestion.get("kind")): str(suggestion.get("value")),
            },
        }
        signals = matched_signals or _string_list(planner_draft.get("expected_matched_signals_contains"))
        if signals:
            case_data["expected_matched_signals_contains"] = signals
        if expected_metric:
            case_data["expected_analysis_request"]["metric"] = expected_metric

        planner_cases_dir.mkdir(parents=True, exist_ok=True)
        final_path = planner_cases_dir / f"{final_case_id}.json"
        if final_path.exists() and not overwrite:
            raise ValueError(f"Planner golden case already exists: {final_path}")

        validation_output = self._validate_candidate(case_data)
        if validation_output:
            return GoldenPromotionResult(final_case_id, final_path, False, validation_output)

        final_path.write_text(json.dumps(case_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return GoldenPromotionResult(final_case_id, final_path, True, ["planner_golden_case_passed"])

    def _validate_candidate(self, case_data: dict[str, Any]) -> list[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            cases_dir = Path(tmpdir)
            (cases_dir / f"{case_data['case_id']}.json").write_text(
                json.dumps(case_data, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            summary = PlannerGoldenCaseRunner(cases_dir, planner=self.planner).run_all()
        return [result.reason for result in summary.results if not result.passed]


def _require_dict(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Golden case draft is missing {field_name}.")
    return value


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _safe_case_id(value: str) -> str:
    lowered = value.strip().lower()
    safe = re.sub(r"[^a-z0-9_]+", "_", lowered)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        raise ValueError("Golden case id cannot be empty.")
    return safe
