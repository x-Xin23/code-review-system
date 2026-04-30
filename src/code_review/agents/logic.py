from ..models.context import ReviewContext, ReviewPlan
from ..models.findings import Finding, Severity, FindingCategory
from ..prompts.logic import LOGIC_SYSTEM_PROMPT, LOGIC_USER_TEMPLATE
from .base import BaseAgent


class LogicAgent(BaseAgent):
    name = "logic"

    def __init__(self):
        super().__init__()
        self.system_prompt = LOGIC_SYSTEM_PROMPT

    async def analyze(self, context: ReviewContext, plan: ReviewPlan) -> list[Finding]:
        assigned = plan.file_assignments.get("logic", [])
        if not assigned:
            assigned = [f.path for f in context.files]

        file_contents = self._load_file_contents(context, assigned)

        user_message = LOGIC_USER_TEMPLATE.format(
            languages=", ".join(context.languages),
            assigned_files=", ".join(assigned),
            file_contents=file_contents,
        )

        response = await self._call_claude(user_message)
        data = self._parse_json_response(response)

        findings: list[Finding] = []
        for item in data.get("findings", []):
            try:
                finding = Finding(
                    category=FindingCategory.LOGIC,
                    severity=Severity(item.get("severity", "medium")),
                    title=item.get("title", "Untitled"),
                    description=item.get("description", ""),
                    file_path=item.get("file_path", ""),
                    line_range=tuple(item.get("line_range", [0, 0])),
                    code_snippet=item.get("code_snippet", ""),
                    suggestion=item.get("suggestion", ""),
                    confidence=item.get("confidence", 0.8),
                )
                if self._validate_finding(finding):
                    findings.append(finding)
            except Exception:
                continue

        return findings
