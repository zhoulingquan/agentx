from __future__ import annotations

from dataclasses import replace

from .models import TaskPlan, TaskPlanNode
from .subagents import build_default_subagent_registry


class PlanValidationError(ValueError):
    pass


class PlanValidator:
    def validate(self, plan: TaskPlan) -> TaskPlan:
        registry = build_default_subagent_registry()
        node_ids = {node.node_id for node in plan.nodes}
        if len(node_ids) != len(plan.nodes):
            raise PlanValidationError("Task plan contains duplicate node ids.")
        for node in plan.nodes:
            if node.agent_id not in registry:
                raise PlanValidationError(f"Unknown agent in task plan: {node.agent_id}")
            if registry[node.agent_id].runtime_mode != node.runtime_mode:
                raise PlanValidationError(f"Runtime mode mismatch for agent: {node.agent_id}")
            missing = [dependency for dependency in node.depends_on if dependency not in node_ids]
            if missing:
                raise PlanValidationError(f"Node {node.node_id} has unknown dependencies: {missing}")
        return replace(plan, status="frozen")


def default_powerbanana_task_plan() -> TaskPlan:
    return TaskPlan(
        plan_id="plan_powerbanana_v0_1",
        scenario_id="data_file_analysis",
        status="candidate",
        nodes=[
            TaskPlanNode("dag_node_profile", "data_profile_agent", "workflow"),
            TaskPlanNode("dag_node_analysis", "data_analysis_agent", "autonomous", depends_on=["dag_node_profile"]),
            TaskPlanNode("dag_node_report", "report_agent", "workflow", depends_on=["dag_node_analysis"]),
        ],
    )
