from ..models.context import ReviewContext, ReviewPlan
from ..models.findings import Finding, Severity, FindingCategory
from ..prompts.security import SECURITY_SYSTEM_PROMPT, SECURITY_USER_TEMPLATE
from .base import BaseAgent


class SecurityAgent(BaseAgent):
    name = "security"

    def __init__(self):
        super().__init__()
        self.system_prompt = SECURITY_SYSTEM_PROMPT

    async def analyze(self, context: ReviewContext, plan: ReviewPlan) -> list[Finding]:
        assigned = plan.file_assignments.get("security", [])
        if not assigned:
            # If no specific assignment, analyze all files
            assigned = [f.path for f in context.files]

        file_contents = self._load_file_contents(context, assigned)

        user_message = SECURITY_USER_TEMPLATE.format(
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
                    category=FindingCategory.SECURITY,
                    severity=Severity(item.get("severity", "medium")),
                    title=item.get("title", "Untitled"),
                    description=item.get("description", ""),
                    file_path=item.get("file_path", ""),
                    line_range=tuple(item.get("line_range", [0, 0])),
                    code_snippet=item.get("code_snippet", ""),
                    suggestion=item.get("suggestion", ""),
                    cwe_id=item.get("cwe_id"),
                    confidence=item.get("confidence", 0.8),
                )
                if self._validate_finding(finding):
                    findings.append(finding)
            except Exception:
                continue

        return findings
