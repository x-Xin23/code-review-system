from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from uuid import uuid4


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingCategory(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    STANDARDS = "standards"
    LOGIC = "logic"


class Finding(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    category: FindingCategory
    severity: Severity
    title: str
    description: str
    file_path: str
    line_range: tuple[int, int] = (0, 0)
    code_snippet: str = ""
    suggestion: str = ""
    cwe_id: Optional[str] = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    metadata: dict = Field(default_factory=dict)

    def fingerprint(self) -> str:
        """Deterministic hash for deduplication."""
        return f"{self.file_path}:{self.line_range[0]}:{self.category.value}:{self.title[:50]}"
