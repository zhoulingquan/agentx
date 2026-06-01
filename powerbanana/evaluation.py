from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from .models import AnalysisRequest, AnalysisResult, DatasetSnapshot, EvaluationResult, PlannerTrace, SecurityFinding, StepRecord


GATE_ACTION_ORDER = {
    "pass": 0,
    "pass_with_warning": 1,
    "return_partial": 2,
    "needs_clarification": 3,
    "human_review": 4,
    "block": 5,
}


@dataclass(frozen=True)
class EvaluationContext:
    task_id: str
    rows: list[dict[str, str]]
    dataset_snapshot: DatasetSnapshot | None
    analysis_result: AnalysisResult | None
    security_findings: list[SecurityFinding]
    step_trace: list[StepRecord]
    question: str = ""
    planner_trace: PlannerTrace | None = None
    target_type: str = "analysis_result"
    target_ref: str = "blackboard://task_001/artifacts/analysis_result_v1"


@dataclass(frozen=True)
class EvaluatorOutcome:
    evaluator_id: str
    version: str
    passed: bool
    failure_reasons: list[str] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    gate_action: str = "pass"
    evidence_refs: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluator_id": self.evaluator_id,
            "version": self.version,
            "passed": self.passed,
            "failure_reasons": self.failure_reasons,
            "blocking_issues": self.blocking_issues,
            "warnings": self.warnings,
            "scores": self.scores,
            "gate_action": self.gate_action,
            "evidence_refs": self.evidence_refs,
        }


class Evaluator(Protocol):
    evaluator_id: str
    version: str

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        ...


class EvaluationStore(Protocol):
    def persist(self, context: EvaluationContext, result: EvaluationResult) -> str:
        ...


class EvaluatorRegistry:
    def __init__(self, evaluators: list[Evaluator] | None = None) -> None:
        self._evaluators: dict[str, Evaluator] = {}
        for evaluator in evaluators or []:
            self.register(evaluator)

    def register(self, evaluator: Evaluator, replace: bool = False) -> Evaluator:
        if evaluator.evaluator_id in self._evaluators and not replace:
            raise ValueError(f"Evaluator is already registered: {evaluator.evaluator_id}")
        self._evaluators[evaluator.evaluator_id] = evaluator
        return evaluator

    def get(self, evaluator_id: str) -> Evaluator:
        return self._evaluators[evaluator_id]

    def list(self) -> list[Evaluator]:
        return list(self._evaluators.values())


class EvaluationRunner:
    def __init__(self, registry: EvaluatorRegistry | None = None, store: EvaluationStore | None = None) -> None:
        self.registry = registry or default_evaluator_registry()
        self.store = store

    def evaluate_analysis(self, blackboard: Any) -> EvaluationResult:
        context = EvaluationContext(
            task_id=blackboard.task_id,
            rows=blackboard.rows,
            dataset_snapshot=blackboard.dataset_snapshot,
            analysis_result=blackboard.analysis_result,
            security_findings=blackboard.security_findings,
            step_trace=blackboard.step_trace,
            question=blackboard.question,
            planner_trace=blackboard.planner_trace,
            target_ref=f"blackboard://{blackboard.task_id}/artifacts/analysis_result_v1",
        )
        return self.evaluate_context(context)

    def evaluate_planner_trace(self, blackboard: Any) -> EvaluationResult:
        context = EvaluationContext(
            task_id=blackboard.task_id,
            rows=[],
            dataset_snapshot=None,
            analysis_result=None,
            security_findings=[],
            step_trace=[],
            question=blackboard.question,
            planner_trace=blackboard.planner_trace,
            target_type="planner_trace",
            target_ref=(
                f"blackboard://{blackboard.task_id}/planner/{blackboard.planner_trace.candidate_plan_id}"
                if blackboard.planner_trace is not None
                else f"blackboard://{blackboard.task_id}/planner"
            ),
        )
        outcomes = [PlannerIntentEvaluator().evaluate(context)]
        return self._persist(context, aggregate_outcomes(context, outcomes))

    def evaluate_context(self, context: EvaluationContext) -> EvaluationResult:
        outcomes = [evaluator.evaluate(context) for evaluator in self.registry.list()]
        return self._persist(context, aggregate_outcomes(context, outcomes))

    def evaluate_gate(
        self,
        blackboard: Any,
        verdict: str,
        failure_reasons: list[str],
        gate_action: str,
        target_type: str,
        target_ref: str,
        scores: dict[str, float] | None = None,
        blocking_issues: list[str] | None = None,
        warnings: list[str] | None = None,
    ) -> EvaluationResult:
        context = EvaluationContext(
            task_id=blackboard.task_id,
            rows=blackboard.rows,
            dataset_snapshot=blackboard.dataset_snapshot,
            analysis_result=blackboard.analysis_result,
            security_findings=blackboard.security_findings,
            step_trace=blackboard.step_trace,
            target_type=target_type,
            target_ref=target_ref,
        )
        result = make_gate_evaluation(
            verdict=verdict,
            failure_reasons=failure_reasons,
            gate_action=gate_action,
            target_type=target_type,
            target_ref=target_ref,
            scores=scores,
            blocking_issues=blocking_issues,
            warnings=warnings,
            task_id=blackboard.task_id,
        )
        return self._persist(context, result)

    def _persist(self, context: EvaluationContext, result: EvaluationResult) -> EvaluationResult:
        if self.store is None:
            return result
        snapshot_ref = self.store.persist(context, result)
        return replace(result, snapshot_ref=snapshot_ref)


class LocalEvaluationStore:
    def __init__(self, root: Path | str = Path("runs")) -> None:
        self.root = Path(root)
        self.evaluations_path = self.root / "evaluations.jsonl"
        self.snapshots_dir = self.root / "replay_snapshots"

    def persist(self, context: EvaluationContext, result: EvaluationResult) -> str:
        created_at = _utc_now()
        self.root.mkdir(parents=True, exist_ok=True)
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = self._snapshot_path(result.evaluation_id, created_at)
        snapshot_ref = str(snapshot_path)
        result_data = asdict(replace(result, snapshot_ref=snapshot_ref))
        snapshot = {
            "schema_version": "evaluation_replay_snapshot_v1",
            "created_at": created_at,
            "snapshot_ref": snapshot_ref,
            "context": evaluation_context_to_dict(context),
            "evaluation": result_data,
        }
        snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
        record = {
            "schema_version": "evaluation_record_v1",
            "created_at": created_at,
            "task_id": context.task_id,
            "evaluation_id": result.evaluation_id,
            "evaluator_version": result.evaluator_version,
            "target_type": result.target_type,
            "target_ref": result.target_ref,
            "verdict": result.verdict,
            "gate_action": result.gate_action,
            "failure_reasons": result.failure_reasons,
            "blocking_issues": result.blocking_issues,
            "warnings": result.warnings,
            "scores": result.scores,
            "snapshot_ref": snapshot_ref,
        }
        with self.evaluations_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return snapshot_ref

    def _snapshot_path(self, evaluation_id: str, created_at: str) -> Path:
        safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in evaluation_id)
        safe_time = created_at.replace(":", "").replace("-", "").replace(".", "")
        return self.snapshots_dir / f"{safe_time}_{safe_id}.json"


class SchemaEvaluator:
    evaluator_id = "schema_evaluator"
    version = "0.1.0"

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        failures = []
        if context.dataset_snapshot is None:
            failures.append("missing_dataset_snapshot")
        if context.analysis_result is None:
            failures.append("missing_analysis_result")
        return EvaluatorOutcome(
            evaluator_id=self.evaluator_id,
            version=self.version,
            passed=not failures,
            failure_reasons=failures,
            blocking_issues=failures,
            scores={"schema": 1.0 if not failures else 0.0},
            gate_action="pass" if not failures else "block",
        )


class DatasetReferenceEvaluator:
    evaluator_id = "dataset_reference_evaluator"
    version = "0.1.0"

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        snapshot = context.dataset_snapshot
        passed = snapshot is not None and snapshot.dataset_version == "upload_v1"
        failures = [] if passed else ["dataset_version_mismatch"]
        return EvaluatorOutcome(
            evaluator_id=self.evaluator_id,
            version=self.version,
            passed=passed,
            failure_reasons=failures,
            blocking_issues=failures,
            scores={"dataset_ref": 1.0 if passed else 0.0},
            gate_action="pass" if passed else "block",
            evidence_refs=["dataset://task_001/upload_v1"] if passed else [],
        )


class FieldReferenceEvaluator:
    evaluator_id = "field_reference_evaluator"
    version = "0.1.0"

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        snapshot = context.dataset_snapshot
        analysis = context.analysis_result
        if snapshot is None or analysis is None:
            return EvaluatorOutcome(self.evaluator_id, self.version, True)
        passed = analysis.group_by in snapshot.columns
        failures = [] if passed else ["field_reference_missing"]
        return EvaluatorOutcome(
            evaluator_id=self.evaluator_id,
            version=self.version,
            passed=passed,
            failure_reasons=failures,
            scores={"field_reference": 1.0 if passed else 0.0},
            gate_action="pass" if passed else "return_partial",
            evidence_refs=[analysis.evidence_ref] if analysis.evidence_ref else [],
        )


class EvidenceCoverageEvaluator:
    evaluator_id = "evidence_coverage_evaluator"
    version = "0.1.0"

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        analysis = context.analysis_result
        if analysis is None:
            return EvaluatorOutcome(self.evaluator_id, self.version, True)
        step_output_refs = {step.output_ref for step in context.step_trace}
        failures = []
        if not analysis.evidence_ref:
            failures.append("missing_evidence_ref")
        elif analysis.evidence_ref not in step_output_refs:
            failures.append("evidence_ref_not_in_step_trace")
        if not context.step_trace:
            failures.append("missing_step_trace")
        return EvaluatorOutcome(
            evaluator_id=self.evaluator_id,
            version=self.version,
            passed=not failures,
            failure_reasons=failures,
            blocking_issues=failures,
            scores={"evidence_coverage": 1.0 if not failures else 0.0},
            gate_action="pass" if not failures else "block",
            evidence_refs=[analysis.evidence_ref] if analysis.evidence_ref else [],
        )


class MetricRecomputeEvaluator:
    evaluator_id = "metric_recompute_evaluator"
    version = "0.1.0"

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        analysis = context.analysis_result
        if analysis is None:
            return EvaluatorOutcome(self.evaluator_id, self.version, True)
        failures = []
        if analysis.metric not in {"conversion_rate", "revenue", "orders", "visits"}:
            failures.append("unsupported_metric")
        values = self._compute_metric_values(context.rows, analysis.metric, analysis.group_by)
        if not values:
            failures.append("no_valid_denominator" if analysis.metric == "conversion_rate" else "no_valid_metric_values")
            return EvaluatorOutcome(
                evaluator_id=self.evaluator_id,
                version=self.version,
                passed=False,
                failure_reasons=failures,
                scores={"metric_correctness": 0.0},
                gate_action="return_partial",
            )
        rank_direction = self._rank_direction(context)
        ranker = min if rank_direction == "lowest" else max
        expected_top_value, expected_value = ranker(values.items(), key=lambda item: item[1])
        if analysis.top_value != expected_top_value:
            failures.append("top_value_mismatch")
        if abs(analysis.value - expected_value) > 1e-9:
            failures.append("metric_value_mismatch")
        for group_value, expected_metric_value in values.items():
            actual_value = analysis.values.get(group_value)
            if actual_value is None or abs(actual_value - expected_metric_value) > 1e-9:
                failures.append("metric_values_mismatch")
                break
        return EvaluatorOutcome(
            evaluator_id=self.evaluator_id,
            version=self.version,
            passed=not failures,
            failure_reasons=failures,
            blocking_issues=failures,
            scores={"metric_correctness": 1.0 if not failures else 0.0},
            gate_action="pass" if not failures else "block",
            evidence_refs=[analysis.evidence_ref] if analysis.evidence_ref else [],
        )

    def _rank_direction(self, context: EvaluationContext) -> str:
        request = context.planner_trace.analysis_request if context.planner_trace else None
        return request.rank_direction if request else "highest"

    def _compute_metric_values(self, rows: list[dict[str, str]], metric: str, group_by: str) -> dict[str, float]:
        if metric == "conversion_rate":
            return self._compute_conversion_rates(rows, group_by)
        return self._compute_grouped_sums(rows, metric, group_by)

    def _compute_conversion_rates(self, rows: list[dict[str, str]], group_by: str) -> dict[str, float]:
        grouped: dict[str, dict[str, float]] = {}
        for row in rows:
            group_value = str(row.get(group_by, "")).strip()
            visits = _to_float(row.get("visits"))
            orders = _to_float(row.get("orders"))
            if not group_value or visits is None or orders is None:
                continue
            if group_value not in grouped:
                grouped[group_value] = {"visits": 0.0, "orders": 0.0}
            grouped[group_value]["visits"] += visits
            grouped[group_value]["orders"] += orders
        return {
            group_value: totals["orders"] / totals["visits"]
            for group_value, totals in grouped.items()
            if totals["visits"] > 0
        }

    def _compute_grouped_sums(self, rows: list[dict[str, str]], metric: str, group_by: str) -> dict[str, float]:
        grouped: dict[str, float] = {}
        for row in rows:
            group_value = str(row.get(group_by, "")).strip()
            metric_value = _to_float(row.get(metric))
            if not group_value or metric_value is None:
                continue
            grouped[group_value] = grouped.get(group_value, 0.0) + metric_value
        return grouped


class ContextSecurityEvaluator:
    evaluator_id = "context_security_evaluator"
    version = "0.1.0"

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        unsafe_findings = [
            finding
            for finding in context.security_findings
            if finding.action != "exclude_as_instruction_keep_as_data"
        ]
        warnings = ["prompt_injection_findings_detected"] if context.security_findings else []
        failures = ["unsafe_security_finding_action"] if unsafe_findings else []
        return EvaluatorOutcome(
            evaluator_id=self.evaluator_id,
            version=self.version,
            passed=not unsafe_findings,
            failure_reasons=failures,
            warnings=warnings,
            scores={"context_security": 1.0 if not unsafe_findings else 0.0},
            gate_action="pass" if not unsafe_findings else "human_review",
        )


class PlannerIntentEvaluator:
    evaluator_id = "planner_intent_evaluator"
    version = "0.1.0"

    def evaluate(self, context: EvaluationContext) -> EvaluatorOutcome:
        trace = context.planner_trace
        failures: list[str] = []
        blocking_issues: list[str] = []
        warnings: list[str] = []
        score = 1.0

        if trace is None:
            failures.append("missing_planner_trace")
            blocking_issues.append("missing_planner_trace")
            score = 0.0
        elif trace.intent is None:
            failures.append("missing_planner_intent")
            blocking_issues.append("missing_planner_intent")
            score = 0.0
        else:
            intent = trace.intent
            if intent.scenario_id != trace.scenario_id:
                failures.append("planner_scenario_mismatch")
                blocking_issues.append("planner_scenario_mismatch")
                score = 0.0
            if intent.scenario_id != "unknown" and intent.confidence < 0.5:
                failures.append("planner_confidence_too_low")
                blocking_issues.append("planner_confidence_too_low")
                score = 0.0
            if intent.scenario_id.startswith("unsupported_") and "unsupported_capability" not in intent.warnings:
                failures.append("missing_unsupported_warning")
                blocking_issues.append("missing_unsupported_warning")
                score = 0.0
            if intent.scenario_id == "ambiguous_metric" and "missing_metric" not in intent.warnings:
                failures.append("missing_metric_warning")
                blocking_issues.append("missing_metric_warning")
                score = 0.0
            if (
                intent.scenario_id in {"metric_analysis", "conversion_rate_analysis"}
                and trace.analysis_request is None
                and "needs_vocabulary_suggestion" not in trace.warnings
            ):
                failures.append("missing_analysis_request")
                blocking_issues.append("missing_analysis_request")
                score = 0.0
            warnings = [*intent.warnings, *[warning for warning in trace.warnings if warning not in intent.warnings]]

        return EvaluatorOutcome(
            evaluator_id=self.evaluator_id,
            version=self.version,
            passed=not failures,
            failure_reasons=failures,
            blocking_issues=blocking_issues,
            warnings=warnings,
            scores={"planner_intent": score},
            gate_action="pass" if not failures else "block",
            evidence_refs=[context.target_ref] if context.target_ref else [],
        )


def default_evaluator_registry() -> EvaluatorRegistry:
    return EvaluatorRegistry(
        [
            SchemaEvaluator(),
            DatasetReferenceEvaluator(),
            FieldReferenceEvaluator(),
            EvidenceCoverageEvaluator(),
            MetricRecomputeEvaluator(),
            ContextSecurityEvaluator(),
        ]
    )


def aggregate_outcomes(context: EvaluationContext, outcomes: list[EvaluatorOutcome]) -> EvaluationResult:
    gate_action = _strongest_gate_action([outcome.gate_action for outcome in outcomes])
    failure_reasons = _dedupe(reason for outcome in outcomes for reason in outcome.failure_reasons)
    blocking_issues = _dedupe(issue for outcome in outcomes for issue in outcome.blocking_issues)
    warnings = _dedupe(warning for outcome in outcomes for warning in outcome.warnings)
    evidence_refs = _dedupe(ref for outcome in outcomes for ref in outcome.evidence_refs if ref)
    scores = _merge_scores(outcomes)
    verdict = _verdict_from_gate(gate_action, failure_reasons)
    return EvaluationResult(
        evaluation_id=f"eval_{context.task_id}_analysis_v1",
        evaluator_version=", ".join(f"{outcome.evaluator_id}@{outcome.version}" for outcome in outcomes),
        target_type=context.target_type,
        target_ref=context.target_ref,
        status=_status_from_gate(gate_action),
        verdict=verdict,
        failure_reasons=failure_reasons,
        blocking_issues=blocking_issues,
        warnings=warnings,
        scores=scores,
        gate_action=gate_action,
        evidence_refs=evidence_refs,
        evaluator_results=[outcome.as_dict() for outcome in outcomes],
    )


def make_gate_evaluation(
    verdict: str,
    failure_reasons: list[str],
    gate_action: str,
    target_type: str,
    target_ref: str,
    scores: dict[str, float] | None = None,
    blocking_issues: list[str] | None = None,
    warnings: list[str] | None = None,
    task_id: str = "task_001",
) -> EvaluationResult:
    return EvaluationResult(
        evaluation_id=f"eval_{task_id}_gate_v1",
        evaluator_version="gate_evaluator@0.1.0",
        target_type=target_type,
        target_ref=target_ref,
        status=_status_from_gate(gate_action),
        verdict=verdict,
        failure_reasons=failure_reasons,
        blocking_issues=blocking_issues or [],
        warnings=warnings or [],
        scores=scores or {},
        gate_action=gate_action,
    )


@dataclass(frozen=True)
class ReplayResult:
    snapshot_ref: str
    evaluation_id: str
    changed: bool
    old_verdict: str
    new_verdict: str
    old_gate_action: str
    new_gate_action: str
    differences: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReplaySummary:
    total: int
    unchanged: int
    changed: int
    results: list[ReplayResult] = field(default_factory=list)


class ReplayRunner:
    def __init__(self, registry: EvaluatorRegistry | None = None) -> None:
        self.runner = EvaluationRunner(registry)

    def run_snapshot(self, snapshot_path: Path | str) -> ReplayResult:
        path = Path(snapshot_path)
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        context = evaluation_context_from_dict(snapshot["context"])
        old_evaluation = snapshot["evaluation"]
        new_evaluation = self.runner.evaluate_context(context)
        differences = _evaluation_differences(old_evaluation, asdict(new_evaluation))
        return ReplayResult(
            snapshot_ref=str(path),
            evaluation_id=str(old_evaluation.get("evaluation_id", "")),
            changed=bool(differences),
            old_verdict=str(old_evaluation.get("verdict", "")),
            new_verdict=new_evaluation.verdict,
            old_gate_action=str(old_evaluation.get("gate_action", "")),
            new_gate_action=new_evaluation.gate_action,
            differences=differences,
        )

    def run_dir(self, snapshots_dir: Path | str) -> ReplaySummary:
        results = [self.run_snapshot(path) for path in sorted(Path(snapshots_dir).glob("*.json"))]
        changed = sum(1 for result in results if result.changed)
        return ReplaySummary(
            total=len(results),
            unchanged=len(results) - changed,
            changed=changed,
            results=results,
        )


def evaluation_context_to_dict(context: EvaluationContext) -> dict[str, Any]:
    return asdict(context)


def evaluation_context_from_dict(data: dict[str, Any]) -> EvaluationContext:
    return EvaluationContext(
        task_id=data["task_id"],
        rows=data.get("rows", []),
        dataset_snapshot=_dataset_snapshot_from_dict(data.get("dataset_snapshot")),
        analysis_result=_analysis_result_from_dict(data.get("analysis_result")),
        security_findings=[SecurityFinding(**item) for item in data.get("security_findings", [])],
        step_trace=[StepRecord(**item) for item in data.get("step_trace", [])],
        question=data.get("question", ""),
        planner_trace=_planner_trace_from_dict(data.get("planner_trace")),
        target_type=data.get("target_type", "analysis_result"),
        target_ref=data.get("target_ref", "blackboard://task_001/artifacts/analysis_result_v1"),
    )


def _dataset_snapshot_from_dict(data: dict[str, Any] | None) -> DatasetSnapshot | None:
    if data is None:
        return None
    return DatasetSnapshot(**data)


def _analysis_result_from_dict(data: dict[str, Any] | None) -> AnalysisResult | None:
    if data is None:
        return None
    return AnalysisResult(**data)


def _planner_trace_from_dict(data: dict[str, Any] | None) -> PlannerTrace | None:
    if data is None:
        return None
    intent_data = data.get("intent")
    if intent_data is not None and not hasattr(intent_data, "scenario_id"):
        from .models import PlannerIntent

        data = {**data, "intent": PlannerIntent(**intent_data)}
    request_data = data.get("analysis_request")
    if request_data is not None and not hasattr(request_data, "metric"):
        data = {**data, "analysis_request": AnalysisRequest(**request_data)}
    return PlannerTrace(**data)


def _evaluation_differences(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    differences = []
    for field_name in [
        "verdict",
        "gate_action",
        "failure_reasons",
        "blocking_issues",
        "warnings",
        "scores",
        "evaluator_version",
    ]:
        if old.get(field_name) != new.get(field_name):
            differences.append(f"{field_name}: {old.get(field_name)!r} -> {new.get(field_name)!r}")
    return differences


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _to_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _strongest_gate_action(actions: list[str]) -> str:
    if not actions:
        return "pass"
    return max(actions, key=lambda action: GATE_ACTION_ORDER.get(action, 0))


def _status_from_gate(gate_action: str) -> str:
    if gate_action == "pass":
        return "passed"
    if gate_action == "pass_with_warning":
        return "passed_with_warning"
    if gate_action == "return_partial":
        return "partial"
    if gate_action == "needs_clarification":
        return "needs_clarification"
    if gate_action == "human_review":
        return "needs_human_review"
    return "blocked"


def _verdict_from_gate(gate_action: str, failure_reasons: list[str]) -> str:
    if gate_action in {"pass", "pass_with_warning"} and not failure_reasons:
        return "pass"
    if gate_action == "return_partial":
        return "partial"
    if gate_action == "needs_clarification":
        return "needs_clarification"
    return "fail"


def _dedupe(values: Any) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _merge_scores(outcomes: list[EvaluatorOutcome]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for outcome in outcomes:
        for key, value in outcome.scores.items():
            score_key = key if key not in scores else f"{outcome.evaluator_id}.{key}"
            scores[score_key] = value
    return scores
