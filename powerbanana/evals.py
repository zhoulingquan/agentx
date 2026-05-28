from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .agent import PowerBananaAgent


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
        checks = [
            report.status == data["expected_status"],
            report.answer == data["expected_answer"],
        ]
        if "expected_top_value" in data:
            checks.append(report.analysis_result is not None and report.analysis_result.top_value == data["expected_top_value"])
        if all(checks):
            return GoldenCaseResult(case_id=data["case_id"], passed=True)
        return GoldenCaseResult(case_id=data["case_id"], passed=False, reason=f"Unexpected report: {report.answer}")
