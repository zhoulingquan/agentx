from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .models import PlannerTrace, TaskPlan
from .plan import default_powerbanana_task_plan
from .planner_lexicon import PlannerClassifier, PlannerLexicon, default_planner_lexicon


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

    def __init__(self, lexicon: PlannerLexicon | None = None) -> None:
        self.lexicon = lexicon or default_planner_lexicon()
        self.classifier = PlannerClassifier(self.lexicon)

    def plan(self, file_path: Path, question: str) -> PlannerResult:
        candidate_plan = default_powerbanana_task_plan()
        intent = self.classifier.classify(question)
        return PlannerResult(
            candidate_plan=candidate_plan,
            trace=PlannerTrace(
                planner_id=self.planner_id,
                planner_mode=self.planner_mode,
                status="candidate_created",
                scenario_id=intent.scenario_id,
                candidate_plan_id=candidate_plan.plan_id,
                rationale=(
                    "Classified the user question with the planner lexicon, then used the fixed "
                    "Phase 1 data-file analysis DAG: profile -> analysis -> report."
                ),
                warnings=intent.warnings,
                intent=intent,
                lexicon_version=self.lexicon.version,
            ),
        )
