from __future__ import annotations

from .blackboard import TaskBlackboard
from .models import MemoryRecord


class MemoryManager:
    def write_task_summary(self, blackboard: TaskBlackboard) -> MemoryRecord:
        record = MemoryRecord(
            memory_id="mem_task_001_summary",
            scope="local",
            layer="working",
            memory_type="task_summary",
            content={
                "status": blackboard.status,
                "answer": blackboard.answer,
                "dataset_version": "upload_v1",
            },
        )
        blackboard.write_memory(record)
        return record
