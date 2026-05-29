from __future__ import annotations

from dataclasses import replace

from .models import TaskPlan, TaskPlanNode
from .subagents import build_default_subagent_registry


class PlanValidationError(ValueError):
    pass


class PlanValidator:
    def validate(self, plan: TaskPlan) -> TaskPlan:
        registry = build_default_subagent_registry()
        if not plan.nodes:
            raise PlanValidationError("Task plan cannot be empty.")
        node_ids = {node.node_id for node in plan.nodes}
        if len(node_ids) != len(plan.nodes):
            raise PlanValidationError("Task plan contains duplicate node ids.")
        for node in plan.nodes:
            if node.agent_id not in registry:
                raise PlanValidationError(f"Unknown agent in task plan: {node.agent_id}")
            if registry[node.agent_id].runtime_mode != node.runtime_mode:
                raise PlanValidationError(f"Runtime mode mismatch for agent: {node.agent_id}")
            if len(set(node.depends_on)) != len(node.depends_on):
                raise PlanValidationError(f"Node {node.node_id} contains duplicate dependencies.")
            missing = [dependency for dependency in node.depends_on if dependency not in node_ids]
            if missing:
                raise PlanValidationError(f"Node {node.node_id} has unknown dependencies: {missing}")
        self._reject_cycles(plan.nodes)
        self._validate_single_root(plan.nodes)
        self._validate_scenario_pattern(plan)
        return replace(plan, status="frozen")

    def _reject_cycles(self, nodes: list[TaskPlanNode]) -> None:
        node_by_id = {node.node_id: node for node in nodes}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            if node_id in visiting:
                raise PlanValidationError(f"Task plan contains a dependency cycle at node {node_id}.")
            visiting.add(node_id)
            for dependency in node_by_id[node_id].depends_on:
                visit(dependency)
            visiting.remove(node_id)
            visited.add(node_id)

        for node in nodes:
            visit(node.node_id)

    def _validate_single_root(self, nodes: list[TaskPlanNode]) -> None:
        roots = [node.node_id for node in nodes if not node.depends_on]
        if len(roots) != 1:
            raise PlanValidationError(f"Task plan is disconnected; it must have exactly one root node, got {roots}.")

    def _validate_scenario_pattern(self, plan: TaskPlan) -> None:
        if plan.scenario_id != "data_file_analysis":
            return
        expected = [
            ("dag_node_profile", "data_profile_agent", "workflow", []),
            ("dag_node_analysis", "data_analysis_agent", "autonomous", ["dag_node_profile"]),
            ("dag_node_report", "report_agent", "workflow", ["dag_node_analysis"]),
        ]
        actual = [
            (node.node_id, node.agent_id, node.runtime_mode, node.depends_on)
            for node in plan.nodes
        ]
        if actual != expected:
            raise PlanValidationError("data_file_analysis task plan pattern mismatch.")


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
