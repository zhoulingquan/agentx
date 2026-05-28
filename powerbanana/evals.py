from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agent import PowerBananaAgent
from .evaluation import EvaluationRunner, evaluation_context_from_dict
from .planner import DeterministicDataFilePlanner


@dataclass(frozen=True)
class GoldenCaseResult:
    case_id: str
    passed: bool
    reason: str = ""


@dataclass(frozen=True)
class GoldenCaseSummary:
    total: int
    passed: int
    failed: int
    results: list[GoldenCaseResult] = field(default_factory=list)


@dataclass(frozen=True)
class CalibrationCaseResult:
    case_id: str
    passed: bool
    expected_gate_action: str
    actual_gate_action: str
    reason: str = ""
    classification: str = ""


@dataclass(frozen=True)
class CalibrationSummary:
    total: int
    passed: int
    failed: int
    false_pass: int
    false_fail: int
    escalation_miss: int
    over_escalation: int
    results: list[CalibrationCaseResult] = field(default_factory=list)


@dataclass(frozen=True)
class PlannerGoldenCaseResult:
    case_id: str
    passed: bool
    expected_scenario: str
    actual_scenario: str
    reason: str = ""


@dataclass(frozen=True)
class PlannerGoldenCaseSummary:
    total: int
    passed: int
    failed: int
    results: list[PlannerGoldenCaseResult] = field(default_factory=list)


class GoldenCaseRunner:
    def __init__(self, cases_dir: Path) -> None:
        self.cases_dir = cases_dir

    def run_all(self) -> GoldenCaseSummary:
        results = [self._run_case(path) for path in sorted(self.cases_dir.glob("*.json"))]
        passed = sum(1 for result in results if result.passed)
        return GoldenCaseSummary(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    def _run_case(self, path: Path) -> GoldenCaseResult:
        data = json.loads(path.read_text(encoding="utf-8"))
        dataset_path = (path.parent / data["dataset"]).resolve()
        report = PowerBananaAgent().answer(dataset_path, data["question"])
        failures = self._check_report(report, data)
        if not failures:
            return GoldenCaseResult(case_id=data["case_id"], passed=True)
        return GoldenCaseResult(case_id=data["case_id"], passed=False, reason="; ".join(failures))

    def _check_report(self, report: Any, data: dict[str, Any]) -> list[str]:
        failures: list[str] = []
        self._expect_equal(failures, "status", report.status, data["expected_status"])
        if "expected_answer" in data:
            self._expect_equal(failures, "answer", report.answer, data["expected_answer"])
        if "expected_answer_contains" in data:
            for text in data["expected_answer_contains"]:
                if text not in report.answer:
                    failures.append(f"answer missing text {text!r}")
        if "expected_top_value" in data:
            actual = report.analysis_result.top_value if report.analysis_result is not None else None
            self._expect_equal(failures, "top_value", actual, data["expected_top_value"])
        if "expected_evaluation_verdict" in data:
            self._expect_equal(failures, "evaluation.verdict", report.evaluation.verdict, data["expected_evaluation_verdict"])
        if "expected_gate_action" in data:
            self._expect_equal(failures, "evaluation.gate_action", report.evaluation.gate_action, data["expected_gate_action"])
        if "expected_failure_reasons" in data:
            self._expect_equal(failures, "failure_reasons", report.evaluation.failure_reasons, data["expected_failure_reasons"])
        if "expected_blocking_issues" in data:
            self._expect_equal(failures, "blocking_issues", report.evaluation.blocking_issues, data["expected_blocking_issues"])
        if "expected_warnings" in data:
            self._expect_equal(failures, "warnings", report.evaluation.warnings, data["expected_warnings"])
        if "expected_evaluator_version_contains" in data:
            for text in data["expected_evaluator_version_contains"]:
                if text not in report.evaluation.evaluator_version:
                    failures.append(f"evaluator_version missing text {text!r}")
        if "expected_security_findings_count" in data:
            self._expect_equal(failures, "security_findings_count", len(report.security_findings), data["expected_security_findings_count"])
        if "expected_human_gates_count" in data:
            self._expect_equal(failures, "human_gates_count", len(report.human_gates), data["expected_human_gates_count"])
        if "expected_step_skills" in data:
            self._expect_equal(failures, "step_skills", [step.skill_id for step in report.step_trace], data["expected_step_skills"])
        if "expected_limitations_contains" in data:
            limitations = "\n".join(report.limitations)
            for text in data["expected_limitations_contains"]:
                if text not in limitations:
                    failures.append(f"limitations missing text {text!r}")
        if "expected_row_count" in data:
            self._expect_equal(failures, "row_count", report.dataset_snapshot.row_count, data["expected_row_count"])
        if "expected_columns" in data:
            self._expect_equal(failures, "columns", report.dataset_snapshot.columns, data["expected_columns"])
        if "expected_missing_counts" in data:
            for column, expected_count in data["expected_missing_counts"].items():
                actual_count = report.dataset_snapshot.missing_counts.get(column)
                self._expect_equal(failures, f"missing_counts.{column}", actual_count, expected_count)
        return failures

    def _expect_equal(self, failures: list[str], field_name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            failures.append(f"{field_name} expected {expected!r}, got {actual!r}")


class PlannerGoldenCaseRunner:
    def __init__(self, cases_dir: Path, planner: DeterministicDataFilePlanner | None = None) -> None:
        self.cases_dir = cases_dir
        self.planner = planner or DeterministicDataFilePlanner()

    def run_all(self) -> PlannerGoldenCaseSummary:
        results = [self._run_case(path) for path in sorted(self.cases_dir.glob("*.json"))]
        passed = sum(1 for result in results if result.passed)
        return PlannerGoldenCaseSummary(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            results=results,
        )

    def _run_case(self, path: Path) -> PlannerGoldenCaseResult:
        data = json.loads(path.read_text(encoding="utf-8"))
        planner_result = self.planner.plan(Path(data.get("file_path", "sample.csv")), data["question"])
        intent = planner_result.trace.intent
        if intent is None:
            return PlannerGoldenCaseResult(
                case_id=data["case_id"],
                passed=False,
                expected_scenario=data["expected_scenario"],
                actual_scenario="",
                reason="planner trace did not include intent",
            )
        failures = self._check_intent(intent, data)
        return PlannerGoldenCaseResult(
            case_id=data["case_id"],
            passed=not failures,
            expected_scenario=data["expected_scenario"],
            actual_scenario=intent.scenario_id,
            reason="; ".join(failures),
        )

    def _check_intent(self, intent: Any, data: dict[str, Any]) -> list[str]:
        failures: list[str] = []
        self._expect_equal(failures, "scenario_id", intent.scenario_id, data["expected_scenario"])
        if "expected_min_confidence" in data and intent.confidence < data["expected_min_confidence"]:
            failures.append(
                f"confidence expected >= {data['expected_min_confidence']!r}, got {intent.confidence!r}"
            )
        for signal in data.get("expected_matched_signals_contains", []):
            if signal not in intent.matched_signals:
                failures.append(f"matched_signals missing {signal!r}")
        for warning in data.get("expected_warnings_contains", []):
            if warning not in intent.warnings:
                failures.append(f"warnings missing {warning!r}")
        return failures

    def _expect_equal(self, failures: list[str], field_name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            failures.append(f"{field_name} expected {expected!r}, got {actual!r}")


class CalibrationRunner:
    def __init__(self, cases_dir: Path, evaluation_runner: EvaluationRunner | None = None) -> None:
        self.cases_dir = cases_dir
        self.evaluation_runner = evaluation_runner or EvaluationRunner()

    def run_all(self) -> CalibrationSummary:
        results = [self._run_case(path) for path in sorted(self.cases_dir.glob("*.json"))]
        passed = sum(1 for result in results if result.passed)
        return CalibrationSummary(
            total=len(results),
            passed=passed,
            failed=len(results) - passed,
            false_pass=sum(1 for result in results if result.classification == "false_pass"),
            false_fail=sum(1 for result in results if result.classification == "false_fail"),
            escalation_miss=sum(1 for result in results if result.classification == "escalation_miss"),
            over_escalation=sum(1 for result in results if result.classification == "over_escalation"),
            results=results,
        )

    def _run_case(self, path: Path) -> CalibrationCaseResult:
        data = json.loads(path.read_text(encoding="utf-8"))
        context = evaluation_context_from_dict(data["context"])
        result = self.evaluation_runner.evaluate_context(context)
        failures = self._check_evaluation(result, data)
        classification = self._classify(data["expected_gate_action"], result.gate_action)
        return CalibrationCaseResult(
            case_id=data["case_id"],
            passed=not failures,
            expected_gate_action=data["expected_gate_action"],
            actual_gate_action=result.gate_action,
            reason="; ".join(failures),
            classification="" if not failures else classification,
        )

    def _check_evaluation(self, result: Any, data: dict[str, Any]) -> list[str]:
        failures: list[str] = []
        self._expect_equal(failures, "gate_action", result.gate_action, data["expected_gate_action"])
        if "expected_verdict" in data:
            self._expect_equal(failures, "verdict", result.verdict, data["expected_verdict"])
        if "expected_failure_reasons" in data:
            self._expect_equal(failures, "failure_reasons", result.failure_reasons, data["expected_failure_reasons"])
        if "expected_failure_reasons_contains" in data:
            for reason in data["expected_failure_reasons_contains"]:
                if reason not in result.failure_reasons:
                    failures.append(f"failure_reasons missing {reason!r}")
        if "expected_warnings_contains" in data:
            for warning in data["expected_warnings_contains"]:
                if warning not in result.warnings:
                    failures.append(f"warnings missing {warning!r}")
        if "expected_blocking_issues_contains" in data:
            for issue in data["expected_blocking_issues_contains"]:
                if issue not in result.blocking_issues:
                    failures.append(f"blocking_issues missing {issue!r}")
        return failures

    def _classify(self, expected: str, actual: str) -> str:
        passing = {"pass", "pass_with_warning"}
        if expected == "human_review" and actual != "human_review":
            return "escalation_miss"
        if expected != "human_review" and actual == "human_review":
            return "over_escalation"
        if expected not in passing and actual in passing:
            return "false_pass"
        if expected in passing and actual not in passing:
            return "false_fail"
        return "mismatch"

    def _expect_equal(self, failures: list[str], field_name: str, actual: Any, expected: Any) -> None:
        if actual != expected:
            failures.append(f"{field_name} expected {expected!r}, got {actual!r}")
