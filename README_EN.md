# AI-Driven Full-Chain Code Review & Security Audit System

A multi-agent AI system that performs comprehensive code review across four dimensions: **Security**, **Performance**, **Standards**, and **Logic**.

## Architecture

```
Input (file/dir/diff)
       │
       ▼
┌──────────────┐
│  Orchestrator │  Analyzes codebase, creates review plan
└──────┬───────┘
       │
  ┌────┼────┬────┐
  ▼    ▼    ▼    ▼
┌────┐┌────┐┌────┐┌────┐
│ 🔒  ││ ⚡  ││ 📏  ││ 🧠  │  4 specialized agents
│Sec ││Perf││Std ││Log │  running in parallel
└──┬─┘└──┬─┘└──┬─┘└──┬─┘
   │     │     │     │
   └────┼────┼────┘
        ▼
┌──────────────┐
│  Aggregator   │  Dedup, conflict resolution, risk scoring
└──────┬───────┘
       ▼
  📄 Report (Markdown + HTML)
```

### Agents

| Agent | Focus | Methodology |
|-------|-------|-------------|
| **Orchestrator** | Task decomposition | Analyzes code structure, assigns files, detects dependencies |
| **Security** | Vulnerabilities (OWASP) | 6-step CoT: Input→DataFlow→Sink→Classification→Severity→Fix |
| **Performance** | Efficiency & resources | Complexity analysis, N+1 detection, memory, I/O |
| **Standards** | Code quality | SOLID, naming, error handling, documentation |
| **Logic** | Bugs & edge cases | 6-step CoT: Entry→Paths→Boundaries→State→Concurrency→Business Logic |
| **Aggregator** | Consolidation | 3-tier dedup, conflict resolution, weighted risk scoring |

### Long-Chain Reasoning

The Security and Logic agents use a 6-step chain-of-thought methodology:

**Security Agent Chain**:
1. Input Identification → 2. Data Flow Tracing → 3. Sink Identification → 4. Vulnerability Classification → 5. Severity Assessment → 6. Remediation

**Logic Agent Chain**:
1. Entry Point Analysis → 2. Path Enumeration → 3. Boundary Analysis → 4. State Consistency → 5. Concurrency Analysis → 6. Business Logic Validation

## Installation

```bash
# Clone and enter project
cd code-review

# Install with pip
pip install -e .

# Set up API key
cp .env.example .env
# Edit .env with your Anthropic API key
```

## Usage

### Review a single file
```bash
code-review file app.py --verbose
```

### Review an entire directory
```bash
code-review dir ./src --max-files 20 --format both
```

### Review a git diff
```bash
git diff main > changes.diff
code-review diff changes.diff
```

### Options
```
--output-dir, -o     Output directory for reports (default: ./output)
--format, -f         Report format: md, html, or both (default: both)
--max-files, -m      Max files to review (dir command)
--verbose, -v        Show detailed agent execution info
```

## Report Output

Reports are generated in the output directory:
- `review-<id>.md` — Markdown report with all findings
- `review-<id>.html` — Interactive HTML report with tab filtering, syntax highlighting, and severity badges

## Risk Score

Weighted formula: `(Critical×10 + High×5 + Medium×2 + Low×0.5) / Files × AvgConfidence`

| Score | Risk Level |
|-------|------------|
| 0–25  | Low |
| 26–50 | Medium |
| 51–75 | High |
| 76–100 | Critical |

## Configuration

All settings via `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Anthropic API key (required) |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-6` | Claude model to use |
| `ANTHROPIC_MAX_TOKENS` | `4096` | Max response tokens |
| `ANTHROPIC_THINKING_BUDGET` | `2048` | Extended thinking budget |
| `MAX_FILES_PER_REVIEW` | `50` | Max files per directory review |
| `AGENT_TIMEOUT_SECONDS` | `120` | Timeout per agent call |

## Test Fixtures

The `tests/fixtures/` directory contains intentionally vulnerable code for testing:

- `vulnerable_flask.py` — Python/Flask app with 15+ vulnerabilities (SQLi, XSS, Command Injection, IDOR, etc.)
- `vulnerable_express.js` — Node.js/Express app with 12+ vulnerabilities (NoSQLi, SSRF, Prototype Pollution, etc.)
- `sample.diff` — Git diff containing injected vulnerabilities

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

```
src/code_review/
├── main.py           # CLI entry point & pipeline orchestration
├── config.py          # Pydantic settings from .env
├── models/            # Pydantic data models
│   ├── findings.py    # Finding, Severity, Category
│   ├── context.py     # ReviewContext, FileInfo, Diff
│   └── report.py      # ReviewReport, Summary
├── parser/
│   └── diff_parser.py # Git diff & directory parsing
├── agents/
│   ├── base.py        # Base agent (API, retry, JSON repair)
│   ├── orchestrator.py
│   ├── security.py    # 6-step CoT security audit
│   ├── performance.py
│   ├── standards.py
│   ├── logic.py       # 6-step CoT logic analysis
│   └── aggregator.py  # Dedup + risk scoring
├── prompts/           # System prompt templates
├── reporters/
│   ├── markdown.py
│   └── html.py        # Jinja2 + Pygments highlighting
└── templates/
    └── report.html.jinja2
```

## License

MIT
