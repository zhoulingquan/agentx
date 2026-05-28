from __future__ import annotations

from .blackboard import TaskBlackboard
from .models import ContextBundle, ContextItem


class ContextManager:
    def build_analysis_context(self, blackboard: TaskBlackboard) -> ContextBundle:
        bundle = ContextBundle(
            context_bundle_id="ctx_task_001_analysis_v1",
            agent_id="data_analysis_agent",
            max_tokens=4000,
            items=[
                ContextItem(
                    ref="dataset://task_001/upload_v1",
                    trust_level="untrusted_user_content",
                    allowed_use="data_only",
                ),
                ContextItem(
                    ref="blackboard://task_001/artifacts/data_profile_v1",
                    trust_level="verified_tool_result",
                    allowed_use="evidence",
                ),
            ],
        )
        blackboard.set_context_bundle(bundle)
        return bundle
