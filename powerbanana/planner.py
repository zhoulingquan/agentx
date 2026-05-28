from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import PlannerTrace, TaskPlan
from .plan import default_powerbanana_task_plan


@dataclass(frozen=True)
class PlannerResult:
    candidate_plan: TaskPlan
    trace: PlannerTrace


class Planner(Protocol):
    planner_id: str
    planner_mode: str

    def plan(self, file_path: Path, question: str) -> PlannerResult:
        ...


class DeterministicDataFilePlanner:
    planner_id = "deterministic_data_file_planner"
    planner_mode = "deterministic_no_llm"

    def plan(self, file_path: Path, question: str) -> PlannerResult:
        candidate_plan = default_powerbanana_task_plan()
        return PlannerResult(
            candidate_plan=candidate_plan,
            trace=PlannerTrace(
                planner_id=self.planner_id,
                planner_mode=self.planner_mode,
                status="candidate_created",
                scenario_id=candidate_plan.scenario_id,
                candidate_plan_id=candidate_plan.plan_id,
                rationale="Use fixed Phase 1 data-file analysis DAG: profile -> analysis -> report.",
            ),
        )
