from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter

from ..models.report import ReviewReport

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"


def _highlight_code(code: str, language: str = "python") -> str:
    """Apply syntax highlighting to code snippet."""
    if not code:
        return ""
    try:
        lexer = get_lexer_by_name(language, stripall=True)
    except Exception:
        try:
            lexer = guess_lexer(code)
        except Exception:
            return f"<pre><code>{_escape_html(code)}</code></pre>"

    formatter = HtmlFormatter(style="monokai", cssclass="highlight")
    return highlight(code, lexer, formatter)


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html(report: ReviewReport) -> str:
    """Generate interactive HTML report using Jinja2 template."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html.jinja2")

    # Pre-compute syntax-highlighted code snippets
    for finding in report.findings:
        if finding.code_snippet:
            finding.metadata["highlighted_snippet"] = _highlight_code(
                finding.code_snippet,
                language="python",  # Could detect from file extension
            )

    return template.render(
        report=report,
        summary=report.summary,
        findings=report.findings,
        critical_findings=report.findings_by_severity("critical"),
        high_findings=report.findings_by_severity("high"),
        medium_findings=report.findings_by_severity("medium"),
        low_findings=report.findings_by_severity("low"),
        security_findings=report.findings_by_category("security"),
        performance_findings=report.findings_by_category("performance"),
        standards_findings=report.findings_by_category("standards"),
        logic_findings=report.findings_by_category("logic"),
        risk_level=_risk_level(report.summary.risk_score),
        risk_color=_risk_color(report.summary.risk_score),
    )


def _risk_level(score: float) -> str:
    if score >= 76:
        return "CRITICAL"
    elif score >= 51:
        return "HIGH"
    elif score >= 26:
        return "MEDIUM"
    return "LOW"


def _risk_color(score: float) -> str:
    if score >= 76:
        return "#e74c3c"
    elif score >= 51:
        return "#e67e22"
    elif score >= 26:
        return "#f1c40f"
    return "#27ae60"


def save_html(report: ReviewReport, output_path: Path) -> Path:
    """Save HTML report to file."""
    content = generate_html(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path
