from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .blackboard import TaskBlackboard
from .models import TaskPlan


@dataclass(frozen=True)
class TaskDagNode:
    node_id: str
    agent_id: str
    depends_on: list[str] = field(default_factory=list)


class TaskDagExecutor:
    def __init__(self, nodes: list[TaskDagNode]) -> None:
        self.nodes = nodes

    @classmethod
    def from_plan(cls, plan: TaskPlan) -> "TaskDagExecutor":
        if plan.status != "frozen":
            raise ValueError("TaskDagExecutor requires a frozen task plan.")
        return cls(plan.nodes)

    def run(self, blackboard: TaskBlackboard, handlers: dict[str, Callable[..., object]], file_path: Path, report_context: dict[str, str]) -> object:
        completed: set[str] = set()
        results: dict[str, object] = {}
        for node in self.nodes:
            missing = [dependency for dependency in node.depends_on if dependency not in completed]
            if missing:
                raise ValueError(f"DAG node {node.node_id} has unmet dependencies: {missing}")
            blackboard.record_dag_node(node.node_id, node.agent_id, "running", node.depends_on)
            if node.agent_id == "data_profile_agent":
                result = handlers[node.agent_id](blackboard, file_path)
            elif node.agent_id == "report_agent":
                completed.add(node.node_id)
                blackboard.record_dag_node(node.node_id, node.agent_id, "succeeded", node.depends_on)
                result = handlers[node.agent_id](blackboard, report_context["agent_name"], report_context["version"])
                results[node.node_id] = result
                return result
            else:
                result = handlers[node.agent_id](blackboard)
            completed.add(node.node_id)
            results[node.node_id] = result
            status = "succeeded" if blackboard.status not in {"failed"} else "failed"
            blackboard.record_dag_node(node.node_id, node.agent_id, status, node.depends_on)
            if blackboard.status == "needs_clarification":
                return None
        return results.get(self.nodes[-1].node_id)


def default_powerbanana_task_dag() -> list[TaskDagNode]:
    return [
        TaskDagNode("dag_node_profile", "data_profile_agent"),
        TaskDagNode("dag_node_analysis", "data_analysis_agent", depends_on=["dag_node_profile"]),
        TaskDagNode("dag_node_report", "report_agent", depends_on=["dag_node_analysis"]),
    ]
