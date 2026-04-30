import re
from pathlib import Path
from ..models.context import FileInfo, FileDiff, DiffHunk, ReviewContext

LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".xml": "xml",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
}


def detect_language(filepath: str) -> str:
    ext = Path(filepath).suffix.lower()
    return LANGUAGE_MAP.get(ext, "text")


def parse_diff(diff_text: str) -> list[FileDiff]:
    """Parse unified diff format into structured FileDiff objects."""
    diffs: list[FileDiff] = []
    current_file: FileDiff | None = None
    current_hunk: DiffHunk | None = None
    hunk_lines: list[str] = []

    file_pattern = re.compile(r"^diff --git a/(.+) b/(.+)$")
    old_pattern = re.compile(r"^--- (?:a/)?(.+)$")
    new_pattern = re.compile(r"^\+\+\+ (?:b/)?(.+)$")
    hunk_pattern = re.compile(r"^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@ ?(.*)$")

    for line in diff_text.split("\n"):
        file_match = file_pattern.match(line)
        if file_match:
            if current_file and current_hunk:
                current_hunk.content = "\n".join(hunk_lines)
                current_file.hunks.append(current_hunk)
            if current_file:
                diffs.append(current_file)
            current_file = FileDiff(
                old_path=file_match.group(1),
                new_path=file_match.group(2),
            )
            hunk_lines = []
            current_hunk = None
            continue

        old_match = old_pattern.match(line)
        if old_match and current_file:
            current_file.old_path = old_match.group(1)
            continue

        new_match = new_pattern.match(line)
        if new_match and current_file:
            current_file.new_path = new_match.group(1)
            current_file.language = detect_language(new_match.group(1))
            continue

        hunk_match = hunk_pattern.match(line)
        if hunk_match and current_file:
            if current_hunk:
                current_hunk.content = "\n".join(hunk_lines)
                current_file.hunks.append(current_hunk)
                hunk_lines = []

            old_count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
            new_count = int(hunk_match.group(4)) if hunk_match.group(4) else 1
            current_hunk = DiffHunk(
                old_start=int(hunk_match.group(1)),
                old_count=old_count,
                new_start=int(hunk_match.group(3)),
                new_count=new_count,
                header=hunk_match.group(5).strip(),
            )
            hunk_lines.append(line)
            continue

        if current_hunk:
            hunk_lines.append(line)

    if current_file:
        if current_hunk:
            current_hunk.content = "\n".join(hunk_lines)
            current_file.hunks.append(current_hunk)
        diffs.append(current_file)

    # Mark new/deleted/renamed files
    for d in diffs:
        if d.old_path == "/dev/null":
            d.is_new = True
        elif d.new_path == "/dev/null":
            d.is_deleted = True
        elif d.old_path != d.new_path:
            d.is_rename = True

    return diffs


def read_directory(path: Path, max_files: int = 50) -> list[FileInfo]:
    """Read all source files from a directory recursively."""
    files: list[FileInfo] = []
    extensions = tuple(LANGUAGE_MAP.keys())

    for filepath in path.rglob("*"):
        if filepath.is_file() and filepath.suffix.lower() in extensions:
            if len(files) >= max_files:
                break
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                rel_path = str(filepath.relative_to(path))
                files.append(FileInfo(
                    path=rel_path,
                    language=detect_language(rel_path),
                    content=content,
                    is_new=True,
                ))
            except Exception:
                continue

    return files


def build_context_from_diff(diff_text: str) -> ReviewContext:
    """Build a ReviewContext from git diff text."""
    diffs = parse_diff(diff_text)
    languages: set[str] = set()

    files: list[FileInfo] = []
    total_lines = 0
    for d in diffs:
        languages.add(d.language)
        content_parts = []
        for h in d.hunks:
            total_lines += h.new_count
        files.append(FileInfo(
            path=d.new_path,
            language=d.language,
            content="",  # Diff doesn't have full file content
            is_new=d.is_new,
        ))

    return ReviewContext(files=files, diffs=diffs, total_lines=total_lines, languages=languages)


def build_context_from_directory(path: Path, max_files: int = 50) -> ReviewContext:
    """Build a ReviewContext from a directory of source files."""
    files = read_directory(path, max_files)
    languages: set[str] = {f.language for f in files}
    total_lines = sum(len(f.content.split("\n")) for f in files)

    return ReviewContext(files=files, total_lines=total_lines, languages=languages)


def build_context_from_file(filepath: Path) -> ReviewContext:
    """Build a ReviewContext from a single file."""
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    language = detect_language(str(filepath))
    file_info = FileInfo(
        path=filepath.name,
        language=language,
        content=content,
        is_new=True,
    )
    total_lines = len(content.split("\n"))

    return ReviewContext(
        files=[file_info],
        total_lines=total_lines,
        languages={language},
    )
