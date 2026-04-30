from pydantic import BaseModel, Field
from typing import Optional
from uuid import uuid4


class FileInfo(BaseModel):
    path: str
    language: str
    content: str
    changed_lines: Optional[list[tuple[int, str]]] = None
    is_new: bool = False


class DiffHunk(BaseModel):
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str = ""
    content: str = ""


class FileDiff(BaseModel):
    old_path: str
    new_path: str
    language: str = ""
    hunks: list[DiffHunk] = Field(default_factory=list)
    is_new: bool = False
    is_deleted: bool = False
    is_rename: bool = False


class ReviewContext(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    files: list[FileInfo] = Field(default_factory=list)
    diffs: list[FileDiff] = Field(default_factory=list)
    total_lines: int = 0
    languages: set[str] = Field(default_factory=set)

    @property
    def file_count(self) -> int:
        return len(self.files)


class ReviewPlan(BaseModel):
    context_id: str
    agents_to_run: list[str] = Field(default_factory=list)
    file_assignments: dict[str, list[str]] = Field(default_factory=dict)
    focus_areas: list[str] = Field(default_factory=list)
    dependency_graph: dict[str, list[str]] = Field(default_factory=dict)
    cross_file_concerns: list[str] = Field(default_factory=list)
