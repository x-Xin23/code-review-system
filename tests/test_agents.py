"""Tests for the code review system."""
import pytest
from pathlib import Path

from code_review.models.findings import Finding, Severity, FindingCategory
from code_review.models.context import ReviewContext, FileInfo, ReviewPlan
from code_review.models.report import ReviewReport, ReviewSummary
from code_review.parser.diff_parser import (
    parse_diff,
    detect_language,
    build_context_from_file,
    build_context_from_directory,
)
from code_review.agents.aggregator import AggregatorAgent


class TestModels:
    def test_severity_enum(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"

    def test_finding_creation(self):
        f = Finding(
            category=FindingCategory.SECURITY,
            severity=Severity.CRITICAL,
            title="SQL Injection",
            description="User input flows unsanitized into SQL query",
            file_path="app.py",
            line_range=(42, 42),
            code_snippet="query = f\"SELECT * FROM users WHERE id = {user_id}\"",
            suggestion="Use parameterized queries",
            cwe_id="CWE-89",
            confidence=0.95,
        )
        assert f.category == FindingCategory.SECURITY
        assert f.fingerprint() != ""

    def test_finding_fingerprint_deterministic(self):
        f1 = Finding(
            category=FindingCategory.SECURITY,
            severity=Severity.HIGH,
            title="XSS Vulnerability",
            description="...",
            file_path="app.py",
            line_range=(10, 15),
        )
        f2 = Finding(
            category=FindingCategory.SECURITY,
            severity=Severity.HIGH,
            title="XSS Vulnerability",
            description="...",
            file_path="app.py",
            line_range=(10, 15),
        )
        assert f1.fingerprint() == f2.fingerprint()

    def test_review_summary_defaults(self):
        s = ReviewSummary()
        assert s.total_findings == 0
        assert s.risk_score == 0.0

    def test_review_report_findings_by_severity(self):
        findings = [
            Finding(category=FindingCategory.SECURITY, severity=Severity.CRITICAL,
                    title="C1", description="...", file_path="a.py", line_range=(1,1)),
            Finding(category=FindingCategory.PERFORMANCE, severity=Severity.HIGH,
                    title="H1", description="...", file_path="b.py", line_range=(2,2)),
            Finding(category=FindingCategory.STANDARDS, severity=Severity.MEDIUM,
                    title="M1", description="...", file_path="c.py", line_range=(3,3)),
        ]
        s = ReviewSummary(total_findings=3, critical=1, high=1, medium=1)
        report = ReviewReport(id="test", findings=findings, summary=s)

        assert len(report.findings_by_severity(Severity.CRITICAL)) == 1
        assert len(report.findings_by_severity(Severity.HIGH)) == 1


class TestDiffParser:
    def test_detect_language(self):
        assert detect_language("app.py") == "python"
        assert detect_language("index.js") == "javascript"
        assert detect_language("component.tsx") == "typescript"
        assert detect_language("Main.java") == "java"
        assert detect_language("unknown.xyz") == "text"

    def test_parse_simple_diff(self):
        diff_text = """diff --git a/test.py b/test.py
index 1234..5678 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
     print("Hello")
+    print("World")
"""
        diffs = parse_diff(diff_text)
        assert len(diffs) == 1
        assert diffs[0].new_path == "test.py"
        assert diffs[0].language == "python"
        assert len(diffs[0].hunks) == 1

    def test_parse_multiple_files(self):
        diff_text = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,1 +1,1 @@
-old
+new
diff --git a/b.js b/b.js
--- a/b.js
+++ b/b.js
@@ -1,1 +1,1 @@
-old
+new
"""
        diffs = parse_diff(diff_text)
        assert len(diffs) == 2
        assert diffs[0].new_path == "a.py"
        assert diffs[1].new_path == "b.js"

    def test_new_file_detection(self):
        diff_text = """diff --git a/newfile.py b/newfile.py
new file mode 100644
--- /dev/null
+++ b/newfile.py
@@ -0,0 +1,3 @@
+print("new")
+print("file")
"""
        diffs = parse_diff(diff_text)
        assert diffs[0].is_new is True

    def test_build_context_from_file(self, tmp_path):
        filepath = tmp_path / "test.py"
        filepath.write_text("def foo():\n    return 42\n")
        context = build_context_from_file(filepath)
        assert len(context.files) == 1
        assert context.total_lines == 3
        assert "python" in context.languages


class TestAggregator:
    def test_deduplicate_exact_match(self):
        agent = AggregatorAgent()
        f1 = Finding(
            category=FindingCategory.SECURITY, severity=Severity.HIGH,
            title="SQL Injection in login",
            description="Unsanitized input in SQL query",
            file_path="app.py", line_range=(10, 12),
            confidence=0.9,
        )
        f2 = Finding(
            category=FindingCategory.SECURITY, severity=Severity.HIGH,
            title="SQL Injection in login",
            description="Unsanitized input in SQL query",
            file_path="app.py", line_range=(10, 12),
            confidence=0.7,
        )
        result = agent._deduplicate_findings({"security": [f1, f2]})
        assert len(result) == 1
        assert result[0].confidence == 0.9  # Higher confidence kept

    def test_deduplicate_proximity_match(self):
        agent = AggregatorAgent()
        f1 = Finding(
            category=FindingCategory.SECURITY, severity=Severity.CRITICAL,
            title="XSS in user input",
            description="...",
            file_path="app.py", line_range=(20, 22),
        )
        f2 = Finding(
            category=FindingCategory.SECURITY, severity=Severity.LOW,
            title="XSS in user input",
            description="...",
            file_path="app.py", line_range=(23, 25),  # Within 5 lines
        )
        result = agent._deduplicate_findings({"agent1": [f1], "agent2": [f2]})
        assert len(result) == 1
        assert result[0].severity == Severity.CRITICAL  # Higher severity kept

    def test_calculate_summary(self):
        agent = AggregatorAgent()
        findings = [
            Finding(category=FindingCategory.SECURITY, severity=Severity.CRITICAL,
                    title="C1", description="...", file_path="a.py", line_range=(1,1)),
            Finding(category=FindingCategory.PERFORMANCE, severity=Severity.HIGH,
                    title="H1", description="...", file_path="b.py", line_range=(2,2)),
            Finding(category=FindingCategory.STANDARDS, severity=Severity.MEDIUM,
                    title="M1", description="...", file_path="c.py", line_range=(3,3)),
        ]
        context = ReviewContext(
            files=[FileInfo(path="a.py", language="python", content="x", is_new=True),
                    FileInfo(path="b.py", language="python", content="y", is_new=True),
                    FileInfo(path="c.py", language="python", content="z", is_new=True)],
            total_lines=30,
            languages={"python"},
        )
        summary = agent._calculate_summary(findings, context, 5.0)
        assert summary.total_findings == 3
        assert summary.critical == 1
        assert summary.high == 1
        assert summary.medium == 1
        assert summary.files_reviewed == 3
        assert summary.lines_reviewed == 30
        assert summary.review_time_seconds == 5.0
        assert 0 <= summary.risk_score <= 100
