from __future__ import annotations

from collections import defaultdict

from .models import AnalysisResult, DatasetSnapshot, EvaluationResult, StepRecord


def to_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def compute_grouped_conversion_rate(rows: list[dict[str, str]]) -> tuple[dict[str, float], int]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"visits": 0.0, "orders": 0.0})
    skipped_rows = 0
    for row in rows:
        channel = str(row.get("channel", "")).strip()
        visits = to_float(row.get("visits"))
        orders = to_float(row.get("orders"))
        if not channel or visits is None or orders is None:
            skipped_rows += 1
            continue
        grouped[channel]["visits"] += visits
        grouped[channel]["orders"] += orders

    rates = {
        channel: totals["orders"] / totals["visits"]
        for channel, totals in grouped.items()
        if totals["visits"] > 0
    }
    return rates, skipped_rows


def rank_metric_values(rates: dict[str, float]) -> tuple[str, float]:
    return max(rates.items(), key=lambda item: item[1])


def conversion_rate_step_trace(analysis: AnalysisResult) -> list[StepRecord]:
    return [
        StepRecord(
            step_id="s1",
            action_type="skill",
            skill_id="compute_grouped_metric",
            status="succeeded",
            input_refs=["dataset://task_001/upload_v1"],
            output_ref="blackboard://task_001/artifacts/metric_result_s1_v1",
            expected_output_schema="MetricResult",
        ),
        StepRecord(
            step_id="s2",
            action_type="skill",
            skill_id="rank_metric_values",
            status="succeeded",
            input_refs=["blackboard://task_001/artifacts/metric_result_s1_v1"],
            output_ref=analysis.evidence_ref,
            expected_output_schema="RankedMetricResult",
        ),
    ]


def evaluate_metric(snapshot: DatasetSnapshot, analysis: AnalysisResult) -> EvaluationResult:
    failure_reasons = []
    if snapshot.dataset_version != "upload_v1":
        failure_reasons.append("dataset_version_mismatch")
    if analysis.metric != "conversion_rate":
        failure_reasons.append("metric_mismatch")
    if analysis.group_by not in snapshot.columns:
        failure_reasons.append("field_reference_missing")
    if not analysis.evidence_ref:
        failure_reasons.append("missing_evidence_ref")
    return EvaluationResult(
        verdict="pass" if not failure_reasons else "fail",
        failure_reasons=failure_reasons,
        scores={
            "dataset_ref": 1.0 if snapshot.dataset_version == "upload_v1" else 0.0,
            "field_reference": 1.0 if analysis.group_by in snapshot.columns else 0.0,
            "evidence_coverage": 1.0 if analysis.evidence_ref else 0.0,
            "metric_correctness": 1.0 if analysis.metric == "conversion_rate" else 0.0,
        },
    )
