from ..models.context import ReviewContext, ReviewPlan
from ..prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT, ORCHESTRATOR_USER_TEMPLATE
from .base import BaseAgent


class OrchestratorAgent(BaseAgent):
    name = "orchestrator"

    def __init__(self):
        super().__init__()
        self.system_prompt = ORCHESTRATOR_SYSTEM_PROMPT

    async def analyze(self, context: ReviewContext) -> ReviewPlan:
        """Analyze code context and produce a review plan."""
        # Build file contents string
        file_parts = []
        for f in context.files:
            header = f"=== FILE: {f.path} ({f.language}) ===\n"
            content = f.content[:3000]  # Truncate per file for the orchestrator
            file_parts.append(f"{header}{content}")

        # Also include diff information if available
        for d in context.diffs:
            diff_content = "\n".join(h.content for h in d.hunks)
            header = f"=== DIFF: {d.old_path} -> {d.new_path} ({d.language}) ===\n"
            file_parts.append(f"{header}{diff_content[:2000]}")

        user_message = ORCHESTRATOR_USER_TEMPLATE.format(
            languages=", ".join(context.languages),
            file_count=context.file_count,
            total_lines=context.total_lines,
            file_contents="\n\n".join(file_parts),
        )

        response = await self._call_claude(user_message)
        data = self._parse_json_response(response)

        return ReviewPlan(
            context_id=context.id,
            agents_to_run=data.get("agents_to_run", ["security", "performance", "standards", "logic"]),
            file_assignments=data.get("file_assignments", {}),
            focus_areas=data.get("focus_areas", []),
            dependency_graph=data.get("dependency_graph", {}),
            cross_file_concerns=data.get("cross_file_concerns", []),
        )
