from pathlib import Path
from ..models.report import ReviewReport
from ..models.findings import Severity

SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}


def generate_markdown(report: ReviewReport) -> str:
    """Generate a comprehensive Markdown report."""
    s = report.summary

    lines = [
        "# Code Review Report",
        "",
        f"**Report ID**: `{report.id}`",
        f"**Generated**: {report.generated_at}",
        f"**Files Reviewed**: {s.files_reviewed}",
        f"**Lines Reviewed**: {s.lines_reviewed}",
        f"**Review Time**: {s.review_time_seconds:.1f}s",
        "",
        "---",
        "",
        "## Risk Assessment",
        "",
        f"**Risk Score**: `{s.risk_score}/100` ({_risk_level(s.risk_score)})",
        "",
        "| Severity | Count |",
        "|----------|-------|",
        f"| 🔴 Critical | {s.critical} |",
        f"| 🟠 High | {s.high} |",
        f"| 🟡 Medium | {s.medium} |",
        f"| 🔵 Low | {s.low} |",
        f"| ⚪ Info | {s.info} |",
        f"| **Total** | **{s.total_findings}** |",
        "",
        "### By Category",
        "",
        "| Category | Count |",
        "|----------|-------|",
        f"| 🔒 Security | {s.security_count} |",
        f"| ⚡ Performance | {s.performance_count} |",
        f"| 📏 Standards | {s.standards_count} |",
        f"| 🧠 Logic | {s.logic_count} |",
        "",
        "---",
        "",
    ]

    # Recommendations
    if report.recommendations:
        lines.append("## Top Recommendations")
        lines.append("")
        for i, rec in enumerate(report.recommendations, 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Findings per severity
    for severity in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
        sev_findings = report.findings_by_severity(severity)
        if not sev_findings:
            continue

        lines.append(f"## {SEVERITY_EMOJI[severity]} {severity.value.upper()} Findings ({len(sev_findings)})")
        lines.append("")

        for f in sev_findings:
            lines.append(f"### {f.title}")
            lines.append("")
            lines.append(f"- **Category**: {f.category.value}")
            lines.append(f"- **File**: `{f.file_path}` (lines {f.line_range[0]}-{f.line_range[1]})")
            lines.append(f"- **Confidence**: {f.confidence:.0%}")
            if f.cwe_id:
                lines.append(f"- **CWE**: {f.cwe_id}")
            lines.append("")
            lines.append(f"**Description**: {f.description}")
            lines.append("")
            if f.code_snippet:
                lines.append("```")
                lines.append(f.code_snippet.strip())
                lines.append("```")
                lines.append("")
            if f.suggestion:
                lines.append(f"**Fix**: {f.suggestion}")
                lines.append("")
            lines.append("---")
            lines.append("")

    # Agent statuses
    lines.append("## Agent Execution Status")
    lines.append("")
    for agent, status in report.agent_statuses.items():
        lines.append(f"- **{agent}**: {status}")

    return "\n".join(lines)


def _risk_level(score: float) -> str:
    if score >= 76:
        return "CRITICAL"
    elif score >= 51:
        return "HIGH"
    elif score >= 26:
        return "MEDIUM"
    return "LOW"


def save_markdown(report: ReviewReport, output_path: Path) -> Path:
    """Save Markdown report to file."""
    content = generate_markdown(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
