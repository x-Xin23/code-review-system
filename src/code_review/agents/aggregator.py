import json
from ..models.context import ReviewContext
from ..models.findings import Finding, Severity, FindingCategory
from ..models.report import ReviewReport, ReviewSummary
from ..prompts.aggregator import AGGREGATOR_SYSTEM_PROMPT, AGGREGATOR_USER_TEMPLATE
from .base import BaseAgent


class AggregatorAgent(BaseAgent):
    name = "aggregator"

    def __init__(self):
        super().__init__()
        self.system_prompt = AGGREGATOR_SYSTEM_PROMPT

    async def aggregate(
        self,
        context: ReviewContext,
        agent_results: dict[str, list[Finding]],
        review_time: float,
    ) -> ReviewReport:
        """Aggregate findings from all agents using both programmatic logic and AI analysis."""
        # Step 1: Programmatic deduplication
        deduplicated = self._deduplicate_findings(agent_results)

        # Step 2: AI-assisted aggregation for cross-agent linking and recommendations
        ai_result = await self._ai_aggregate(context, agent_results)

        # Step 3: Merge programmatic dedup with AI insights
        ai_findings = self._merge_ai_insights(deduplicated, ai_result)

        # Step 4: Calculate summary statistics
        summary = self._calculate_summary(ai_findings, context, review_time)

        return ReviewReport(
            id=context.id,
            findings=ai_findings,
            summary=summary,
            recommendations=ai_result.get("recommendations", []),
            agent_statuses={k: "completed" for k in agent_results},
        )

    def _deduplicate_findings(self, agent_results: dict[str, list[Finding]]) -> list[Finding]:
        """Three-tier deduplication."""
        seen: dict[str, Finding] = {}
        all_findings: list[Finding] = []

        for agent_name, findings in agent_results.items():
            for f in findings:
                fp = f.fingerprint()
                if fp in seen:
                    # Exact match: keep higher confidence
                    existing = seen[fp]
                    if f.confidence > existing.confidence:
                        seen[fp] = f
                        all_findings[all_findings.index(existing)] = f
                    continue

                # Proximity match: check same file, nearby lines, same category
                merged = False
                for key, existing in list(seen.items()):
                    if (existing.file_path == f.file_path
                            and existing.category == f.category
                            and abs(existing.line_range[0] - f.line_range[0]) <= 5
                            and existing.title[:30] == f.title[:30]):
                        # Merge: keep higher severity and confidence
                        merged = True
                        sev_order = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}
                        if sev_order.get(f.severity.value, 0) > sev_order.get(existing.severity.value, 0):
                            seen[key] = f
                            all_findings[all_findings.index(existing)] = f
                        break

                if not merged:
                    seen[fp] = f
                    all_findings.append(f)

        return all_findings

    async def _ai_aggregate(self, context: ReviewContext, agent_results: dict[str, list[Finding]]) -> dict:
        """Use AI to cross-link findings and generate recommendations."""
        # Prepare agent findings for AI input
        agent_summaries = []
        for agent_name, findings in agent_results.items():
            finding_dicts = [
                {
                    "id": f.id,
                    "category": f.category.value,
                    "severity": f.severity.value,
                    "title": f.title,
                    "description": f.description[:200],
                    "file_path": f.file_path,
                    "line_range": list(f.line_range),
                    "confidence": f.confidence,
                }
                for f in findings[:20]  # Limit to prevent token overflow
            ]
            agent_summaries.append({
                "agent": agent_name,
                "findings": finding_dicts,
            })

        user_message = AGGREGATOR_USER_TEMPLATE.format(
            files_reviewed=context.file_count,
            lines_reviewed=context.total_lines,
            agent_findings=json.dumps(agent_summaries, indent=2),
        )

        response = await self._call_claude(user_message)
        return self._parse_json_response(response)

    def _merge_ai_insights(self, deduplicated: list[Finding], ai_result: dict) -> list[Finding]:
        """Merge AI recommendations into findings."""
        # Add AI-generated cross-references
        # For now, keep the programmatically deduplicated list
        # AI results are used primarily for recommendations
        return deduplicated

    def _calculate_summary(
        self,
        findings: list[Finding],
        context: ReviewContext,
        review_time: float,
    ) -> ReviewSummary:
        """Calculate review summary with risk score."""
        critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        high = sum(1 for f in findings if f.severity == Severity.HIGH)
        medium = sum(1 for f in findings if f.severity == Severity.MEDIUM)
        low = sum(1 for f in findings if f.severity == Severity.LOW)
        info = sum(1 for f in findings if f.severity == Severity.INFO)

        security_count = sum(1 for f in findings if f.category == FindingCategory.SECURITY)
        performance_count = sum(1 for f in findings if f.category == FindingCategory.PERFORMANCE)
        standards_count = sum(1 for f in findings if f.category == FindingCategory.STANDARDS)
        logic_count = sum(1 for f in findings if f.category == FindingCategory.LOGIC)

        # Weighted risk score
        files_reviewed = max(context.file_count, 1)
        avg_confidence = sum(f.confidence for f in findings) / max(len(findings), 1)
        raw_score = (critical * 10 + high * 5 + medium * 2 + low * 0.5) / files_reviewed * avg_confidence
        risk_score = min(max(raw_score, 0), 100)

        return ReviewSummary(
            total_findings=len(findings),
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            info=info,
            security_count=security_count,
            performance_count=performance_count,
            standards_count=standards_count,
            logic_count=logic_count,
            files_reviewed=context.file_count,
            lines_reviewed=context.total_lines,
            risk_score=round(risk_score, 1),
            review_time_seconds=round(review_time, 2),
        )
