from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Any

from .models import AnalysisRequest, AnalysisResult, DatasetSnapshot, EvaluationResult, StepPlan, StepRecord


@dataclass(frozen=True)
class SkillDefinition:
    skill_id: str
    version: str
    input_schema: str
    output_schema: str
    handler: Callable[..., Any]


class SkillRegistry(dict[str, SkillDefinition]):
    def execute(self, skill_id: str, *args: Any, **kwargs: Any) -> Any:
        return self[skill_id].handler(*args, **kwargs)


def build_default_skill_registry() -> SkillRegistry:
    return SkillRegistry(
        {
            "compute_grouped_metric": SkillDefinition(
                skill_id="compute_grouped_metric",
                version="0.1.0",
                input_schema="Rows,AnalysisRequest",
                output_schema="MetricResult",
                handler=compute_grouped_metric,
            ),
            "rank_metric_values": SkillDefinition(
                skill_id="rank_metric_values",
                version="0.1.0",
                input_schema="MetricResult",
                output_schema="RankedMetricResult",
                handler=rank_metric_values,
            ),
        }
    )


def to_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def compute_grouped_metric(rows: list[dict[str, str]], request: AnalysisRequest) -> tuple[dict[str, float], int]:
    if request.metric == "conversion_rate":
        return compute_grouped_conversion_rate(rows, request.group_by)
    return compute_grouped_sum(rows, request.metric, request.group_by)


def compute_grouped_conversion_rate(rows: list[dict[str, str]], group_by: str = "channel") -> tuple[dict[str, float], int]:
    grouped: dict[str, dict[str, float]] = defaultdict(lambda: {"visits": 0.0, "orders": 0.0})
    skipped_rows = 0
    for row in rows:
        group_value = str(row.get(group_by, "")).strip()
        visits = to_float(row.get("visits"))
        orders = to_float(row.get("orders"))
        if not group_value or visits is None or orders is None:
            skipped_rows += 1
            continue
        grouped[group_value]["visits"] += visits
        grouped[group_value]["orders"] += orders

    rates = {
        group_value: totals["orders"] / totals["visits"]
        for group_value, totals in grouped.items()
        if totals["visits"] > 0
    }
    return rates, skipped_rows


def compute_grouped_sum(rows: list[dict[str, str]], metric: str, group_by: str) -> tuple[dict[str, float], int]:
    grouped: dict[str, float] = defaultdict(float)
    skipped_rows = 0
    for row in rows:
        group_value = str(row.get(group_by, "")).strip()
        metric_value = to_float(row.get(metric))
        if not group_value or metric_value is None:
            skipped_rows += 1
            continue
        grouped[group_value] += metric_value
    return dict(grouped), skipped_rows


def rank_metric_values(values: dict[str, float], rank_direction: str = "highest") -> tuple[str, float]:
    ranker = min if rank_direction == "lowest" else max
    return ranker(values.items(), key=lambda item: item[1])


def metric_step_trace(analysis: AnalysisResult, step_plan: StepPlan | None = None) -> list[StepRecord]:
    idempotency_by_step = {
        step.step_id: step.idempotency_key
        for step in step_plan.steps
    } if step_plan else {}
    return [
        StepRecord(
            step_id="s1",
            action_type="skill",
            skill_id="compute_grouped_metric",
            status="succeeded",
            input_refs=["dataset://task_001/upload_v1"],
            output_ref="blackboard://task_001/artifacts/metric_result_s1_v1",
            expected_output_schema="MetricResult",
            idempotency_key=idempotency_by_step.get("s1", ""),
        ),
        StepRecord(
            step_id="s2",
            action_type="skill",
            skill_id="rank_metric_values",
            status="succeeded",
            input_refs=["blackboard://task_001/artifacts/metric_result_s1_v1"],
            output_ref=analysis.evidence_ref,
            expected_output_schema="RankedMetricResult",
            idempotency_key=idempotency_by_step.get("s2", ""),
        ),
    ]


def conversion_rate_step_trace(analysis: AnalysisResult, step_plan: StepPlan | None = None) -> list[StepRecord]:
    return metric_step_trace(analysis, step_plan)


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
