from __future__ import annotations

from dataclasses import dataclass

from .skills import build_default_skill_registry


@dataclass(frozen=True)
class AutonomyPolicy:
    policy_id: str
    level: int
    max_steps: int
    allowed_skills: list[str]

    def validate_step_plan(self, skill_ids: list[str]) -> None:
        registry = build_default_skill_registry()
        if len(skill_ids) > self.max_steps:
            raise ValueError(f"Step plan exceeds max_steps={self.max_steps}.")
        for skill_id in skill_ids:
            if skill_id not in registry:
                raise ValueError(f"Skill is not registered: {skill_id}")
            if skill_id not in self.allowed_skills:
                raise ValueError(f"Skill is not allowed by {self.policy_id}: {skill_id}")


def default_data_analysis_policy() -> AutonomyPolicy:
    return AutonomyPolicy(
        policy_id="data_analysis_l2_v1",
        level=2,
        max_steps=8,
        allowed_skills=[
            "compute_grouped_metric",
            "rank_metric_values",
        ],
    )
