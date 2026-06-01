from __future__ import annotations

import json
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agent import PowerBananaAgent
from .evals import GoldenCaseRunner, PlannerGoldenCaseRunner
from .planner import DeterministicDataFilePlanner


PLACEHOLDER_QUESTION_PREFIX = "Replace this with a real user question"


@dataclass(frozen=True)
class GoldenPromotionResult:
    case_id: str
    case_path: Path
    validation_passed: bool
    validation_output: list[str]
    dataset_path: Path | None = None


class GoldenCasePromoter:
    def __init__(self, planner: DeterministicDataFilePlanner | None = None, agent: PowerBananaAgent | None = None) -> None:
        self.planner = planner or DeterministicDataFilePlanner()
        self.agent = agent or PowerBananaAgent(planner=self.planner)

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

    def promote_e2e_case(
        self,
        draft_path: Path,
        golden_cases_dir: Path,
        dataset_path: Path,
        question: str | None = None,
        case_id: str | None = None,
        expected_metric: str | None = None,
        overwrite: bool = False,
    ) -> GoldenPromotionResult:
        if not dataset_path.exists():
            raise ValueError(f"Dataset does not exist: {dataset_path}")
        draft = json.loads(draft_path.read_text(encoding="utf-8"))
        suggestion = _require_dict(draft.get("suggestion"), "suggestion")
        e2e_draft = _require_dict(draft.get("end_to_end_case_draft"), "end_to_end_case_draft")
        final_question = (question or str(e2e_draft.get("question", ""))).strip()
        if not final_question or final_question.startswith(PLACEHOLDER_QUESTION_PREFIX):
            raise ValueError("End-to-end golden promotion requires a real question. Pass --question or edit the draft first.")

        final_case_id = _safe_case_id(case_id or str(e2e_draft.get("case_id") or f"{suggestion['value']}_metric_question"))
        golden_cases_dir.mkdir(parents=True, exist_ok=True)
        final_case_path = golden_cases_dir / f"{final_case_id}.json"
        final_dataset_path = golden_cases_dir / f"{final_case_id}{dataset_path.suffix.lower() or '.csv'}"
        if not overwrite:
            for path in [final_case_path, final_dataset_path]:
                if path.exists():
                    raise ValueError(f"End-to-end golden case target already exists: {path}")

        report = self.agent.answer(dataset_path, final_question)
        if report.status != "completed" or report.analysis_result is None:
            reason = report.evaluation.failure_reasons if report.evaluation else []
            raise ValueError(f"End-to-end golden promotion requires a completed report, got {report.status}: {reason}")

        case_data = self._build_e2e_case_data(final_case_id, final_dataset_path.name, final_question, report, expected_metric)
        shutil.copyfile(dataset_path, final_dataset_path)
        final_case_path.write_text(json.dumps(case_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validation_output = self._validate_e2e_candidate(golden_cases_dir, final_case_path.name)
        if validation_output:
            final_case_path.unlink(missing_ok=True)
            final_dataset_path.unlink(missing_ok=True)
            return GoldenPromotionResult(final_case_id, final_case_path, False, validation_output, final_dataset_path)

        return GoldenPromotionResult(final_case_id, final_case_path, True, ["e2e_golden_case_passed"], final_dataset_path)

    def _build_e2e_case_data(
        self,
        case_id: str,
        dataset_name: str,
        question: str,
        report: Any,
        expected_metric: str | None,
    ) -> dict[str, Any]:
        analysis = report.analysis_result
        snapshot = report.dataset_snapshot
        if analysis is None or snapshot is None:
            raise ValueError("Completed report is missing analysis result or dataset snapshot.")
        analysis_result = {
            "metric": expected_metric or analysis.metric,
            "group_by": analysis.group_by,
            "top_value": analysis.top_value,
            "value": analysis.value,
        }
        return {
            "case_id": case_id,
            "dataset": dataset_name,
            "question": question,
            "expected_status": report.status,
            "expected_answer": report.answer,
            "expected_top_value": analysis.top_value,
            "expected_evaluation_verdict": report.evaluation.verdict,
            "expected_gate_action": report.evaluation.gate_action,
            "expected_failure_reasons": report.evaluation.failure_reasons,
            "expected_blocking_issues": report.evaluation.blocking_issues,
            "expected_security_findings_count": len(report.security_findings),
            "expected_human_gates_count": len(report.human_gates),
            "expected_step_skills": [step.skill_id for step in report.step_trace],
            "expected_row_count": snapshot.row_count,
            "expected_columns": snapshot.columns,
            "expected_analysis_result": analysis_result,
        }

    def _validate_e2e_candidate(self, cases_dir: Path, case_filename: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_cases_dir = Path(tmpdir)
            source_case = cases_dir / case_filename
            data = json.loads(source_case.read_text(encoding="utf-8"))
            source_dataset = cases_dir / data["dataset"]
            shutil.copyfile(source_case, temp_cases_dir / source_case.name)
            shutil.copyfile(source_dataset, temp_cases_dir / source_dataset.name)
            summary = GoldenCaseRunner(temp_cases_dir, agent=self.agent).run_all()
        return [result.reason for result in summary.results if not result.passed]

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
