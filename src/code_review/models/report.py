from pydantic import BaseModel, Field
from datetime import datetime
from .findings import Finding, Severity


class ReviewSummary(BaseModel):
    total_findings: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0
    security_count: int = 0
    performance_count: int = 0
    standards_count: int = 0
    logic_count: int = 0
    files_reviewed: int = 0
    lines_reviewed: int = 0
    risk_score: float = 0.0  # 0-100
    review_time_seconds: float = 0.0

    @property
    def severity_breakdown(self) -> dict[str, int]:
        return {
            "critical": self.critical,
            "high": self.high,
            "medium": self.medium,
            "low": self.low,
            "info": self.info,
        }


class ReviewReport(BaseModel):
    id: str
    summary: ReviewSummary = Field(default_factory=ReviewSummary)
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    agent_statuses: dict[str, str] = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def findings_by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    def findings_by_category(self, category: str) -> list[Finding]:
        return [f for f in self.findings if f.category.value == category]
